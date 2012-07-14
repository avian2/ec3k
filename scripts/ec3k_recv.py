#!/usr/bin/env python
from gnuradio import digital
from gnuradio import gr
from gnuradio.gr import firdes

import itertools
import math
import os.path
import osmosdr
import signal
import subprocess
import sys
import tempfile
import threading
import time

class InvalidPacket(Exception): pass

class EnergyCount3KState:
	def __init__(self, hex_bytes):
		bits = self._get_bits(hex_bytes)
		bits = [ not bit for bit in bits ]

		bits = self._descrambler([18, 17, 13, 12, 1], bits)
		bits = [ not bit for bit in bits ]
		
		bits = self._bit_unstuff(bits)

		bits = self._bit_shuffle(bits)
		
		bytes = self._get_bytes(bits)

		self._decode_packet(bytes)

	def _get_bits(self, hex_bytes):
		"""Unpacks hex printed data into individual bits
		"""
		bits = []

		for hex_byte in hex_bytes:
			i = int(hex_byte, 16)
			for n in xrange(8):
				bits.append(bool((i<<n) & 0x80))

		return bits

	def _get_bytes(self, bits):
		"""Shift bits into bytes, MSB first
		"""
		bytes = [0] * (len(bits)/8+1)
		for n, bit in enumerate(bits):
			bytes[n/8] |= (int(bit) << (7-n%8))

		return bytes

	def _bit_shuffle(self, bits):
		"""Weird bit shuffling operation required?
		"""
		nbits = []

		# first, invert byte bit order 
		args = [iter(bits)] * 8
		for bit_group in itertools.izip_longest(fillvalue=False, *args):
			nbits += reversed(bit_group)

		# add 4 zero bits at the start
		nbits = [False]*4 + nbits

		return nbits

	def _descrambler(self, taps, bits):
		"""Multiplicative, self-synchronizing scrambler
		"""
		nbits = []

		state = [ False ] * max(taps)

		for bit in bits:

			out = bit
			for tap in taps:
				out = out ^ state[tap-1]
			nbits.append(out)

			state = [ bit ] + state[:-1]

		return nbits

	def _bit_unstuff(self, bits):
		"""Bit stuffing reversal.
		
		6 consecutive 1s serve as a packet start/stop condition.
		In the packet, one zero is stuffed after 5 consecutive 1s
		"""
		nbits = []

		start = False

		cnt = 0
		for n, bit in enumerate(bits):
			if bit:
				cnt += 1
				if start:
					nbits.append(bit)
			else:
				if cnt < 5:
					if start:
						nbits.append(bit)
				elif cnt == 5:
					pass
				elif cnt == 6:
					start = not start
				else:
					raise InvalidPacket("Wrong bit stuffing: %d concecutive ones" % cnt)

				cnt = 0

		return nbits

	def _unpack_int(self, bytes):
		i = 0
		for byte in bytes:
			i = (i * 0x100) + byte

		return i

	def _decode_packet(self, bytes):
		if len(bytes) != 43:
			raise InvalidPacket("Wrong length: %d" % len(bytes))

		self.id			= self._unpack_int(bytes[1:3])
		self.uptime		= self._unpack_int(bytes[3:5])
		self.since_reset	= self._unpack_int(bytes[5:9])
		self.energy_1		= self._unpack_int(bytes[9:16])
		self.current_power	= self._unpack_int(bytes[16:18])/10.0
		self.max_power		= self._unpack_int(bytes[18:20])/10.0
		self.energy_2		= self._unpack_int(bytes[20:23])
		self.timestamp		= time.time()

		# TODO: checksum checking

	def __str__(self):
		return	("id              : %04x\n"
			"uptime          : %d seconds\n"
			"since last reset: %d seconds\n"
			"energy          : %d Ws\n"
			"current power   : %.1f W\n"
			"max power       : %.1f W\n"
			"energy          : %d Ws") % (
					self.id,
					self.uptime,
					self.since_reset,
					self.energy_1,
					self.current_power,
					self.max_power,
					self.energy_2)

class EnergyCount3K:
	def __init__(self, id=None, callback=None):
		"""Create a new EnergyCount3K object

		id: ID of the device to monitor
		callback: optional callable to call on each update
		"""
		self.id = id
		self.callback = callback

		self.want_stop = True
		self.state = None
		self.noise_level = -90

	def start(self):
		"""Start the receiver
		"""
		assert self.want_stop

		self.want_stop = False
		self.threads = []

		self.tempdir = tempfile.mkdtemp()
		self.pipe = os.path.join(self.tempdir, "ec3k.pipe")
		os.mkfifo(self.pipe)

		capture_thread = threading.Thread(target=self._capture_thread)
		capture_thread.start()
		self.threads.append(capture_thread)

		time.sleep(3)

		self._setup_top_block()
		self.tb.start()

	def stop(self):
		"""Stop the receiver, clean up
		"""
		assert not self.want_stop

		self.tb.stop()

		self.want_stop = True

		for thread in self.threads:
			thread.join()

		os.unlink(self.pipe)
		os.rmdir(self.tempdir)

	def get(self):
		"""Get the last received state
		"""
		return self.state

	def _log(self, msg):
		"""Override this method to capture debug info
		"""
		pass

	def _capture_thread(self):
		p = subprocess.Popen(
				["/home/avian/dev/ec3k/am433-0.0.4/am433/capture",
				"-f", self.pipe ],
				bufsize=1,
				stdout=subprocess.PIPE)

		while not self.want_stop:
			line = p.stdout.readline()
			fields = line.split()
			if fields and (fields[0] == 'data'):
				self._log("Decoding packet")
				try:
					state = EnergyCount3KState(fields[1:])
				except InvalidPacket, e:
					self._log("Invalid packet: %s" % (e,))
					continue

				if (not self.id) or (state.id == self.id):
					self.state = state
					if self.callback:
						self.callback(self.state)

	def _noise_probe_thread(self):
		while not self.want_stop:
			power = self.noise_probe.level()

			self.noise_level = 10 * math.log10(max(1e-9, power))
			self._log("Current noise level: %.1f dB" % (self.noise_level,))

			self.squelch.set_threshold(self.noise_level+7.0)
			time.sleep(1.0)

	def _setup_top_block(self):

		self.tb = gr.top_block()

		samp_rate = 96000
		oversample = 10
		center_freq = 868.402e6

		# Radio receiver, initial downsampling
		osmosdr_source = osmosdr.source_c(args="nchan=1 rtl=0,buffers=16")
		osmosdr_source.set_sample_rate(samp_rate*oversample)
		osmosdr_source.set_center_freq(center_freq, 0)
		osmosdr_source.set_freq_corr(0, 0)
		osmosdr_source.set_gain_mode(1, 0)
		osmosdr_source.set_gain(0, 0)

		low_pass_filter = gr.fir_filter_ccf(oversample, 
				firdes.low_pass(1, samp_rate*oversample, 90e3, 8e3, firdes.WIN_HAMMING, 6.76))

		self.tb.connect((osmosdr_source, 0), (low_pass_filter, 0))

		# Squelch
		self.noise_probe = gr.probe_avg_mag_sqrd_c(0, 1.0/samp_rate/1e2)
		self.squelch = gr.simple_squelch_cc(self.noise_level, 1)

		noise_probe_thread = threading.Thread(target=self._noise_probe_thread)
		noise_probe_thread.start()
		self.threads.append(noise_probe_thread)

		self.tb.connect((low_pass_filter, 0), (self.noise_probe, 0))
		self.tb.connect((low_pass_filter, 0), (self.squelch, 0))

		# FM demodulation
		quadrature_demod = gr.quadrature_demod_cf(1)

		self.tb.connect((self.squelch, 0), (quadrature_demod, 0))

		# Binary slicing, transformation into capture-compatible format

		add_offset = gr.add_const_vff((-1e-3, ))

		binary_slicer = digital.binary_slicer_fb()

		char_to_float = gr.char_to_float(1, 1)

		multiply_const = gr.multiply_const_vff((255, ))

		float_to_uchar = gr.float_to_uchar()

		pipe_sink = gr.file_sink(gr.sizeof_char*1, self.pipe)
		pipe_sink.set_unbuffered(False)

		self.tb.connect((quadrature_demod, 0), (add_offset, 0))
		self.tb.connect((add_offset, 0), (binary_slicer, 0))
		self.tb.connect((binary_slicer, 0), (char_to_float, 0))
		self.tb.connect((char_to_float, 0), (multiply_const, 0))
		self.tb.connect((multiply_const, 0), (float_to_uchar, 0))
		self.tb.connect((float_to_uchar, 0), (pipe_sink, 0))

want_stop = False

def handler(signum, frame):
	global want_stop
	print "Signal %d caught! Stopping..." % (signum,)
	want_stop = True

def callback(state):
	print state

def main():
	signal.signal(signal.SIGTERM, handler)
	signal.signal(signal.SIGINT, handler)

	ec3k = EnergyCount3K(callback=callback)

	ec3k.start()

	while not want_stop:
		time.sleep(2)
		print "Noise level: %.1f dB" % ec3k.noise_level

	ec3k.stop()

if __name__ == '__main__':
	main()
