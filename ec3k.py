"""Software receiver for EnergyCount 3000
Copyright (C) 2015  Tomaz Solc <tomaz.solc@tablix.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from gnuradio import digital
from gnuradio import gr, blocks, filter, analog

import itertools
import math
import os.path
import osmosdr
import select
import signal
import subprocess
import tempfile
import threading
import time

def which(program):
	for path in os.environ["PATH"].split(os.pathsep):
		fpath = os.path.join(path, program)
		if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
			return fpath

	return None

class InvalidPacket(Exception): pass

class EnergyCount3KState:
	"""EnergyCount 3000 transmitter state.

	This object contains fields contained in a single radio
	packet:

	id -- 16-bit ID of the device

	time_total -- time in seconds since last reset
	time_on -- time in seconds since last reset with non-zero device power

	energy -- total energy in Ws (watt-seconds)

	power_current -- current device power in watts
	power_max -- maximum device power in watts (reset at unknown intervals)

	reset_counter -- total number of transmitter resets

	device_on_flag -- true if device is currently drawing non-zero power

	timestamp -- UNIX timestamp of the packet reception (not accurate)
	"""
	
	CRC = 0xf0b8

	def __init__(self, hex_bytes):
		bits = self._get_bits(hex_bytes)
		bits = [ not bit for bit in bits ]

		bits = self._descrambler([18, 17, 13, 12, 1], bits)
		bits = [ not bit for bit in bits ]
		
		bits = self._bit_unstuff(bits)

		bits = self._bit_shuffle(bits)

		nibbles = self._get_nibbles(bits)

		self._check_crc(nibbles)
		self._decode_packet(nibbles)

	def _get_bits(self, hex_bytes):
		"""Unpacks hex printed data into individual bits"""
		bits = []

		for hex_byte in hex_bytes:
			i = int(hex_byte, 16)
			for n in xrange(8):
				bits.append(bool((i<<n) & 0x80))

		return bits

	def _get_nibbles(self, bits):
		"""Shift bits into bytes, MSB first"""
		nibbles = [0] * (len(bits) / 4)
		for n, bit in enumerate(bits):
			nibbles[n/4] |= (int(bit) << (3-n%4))

		return nibbles

	def _bit_shuffle(self, bits):
		"""Weird bit shuffling operation required"""
		nbits = []

		# first, invert byte bit order 
		args = [iter(bits)] * 8
		for bit_group in itertools.izip_longest(fillvalue=False, *args):
			nbits += reversed(bit_group)

		return nbits

	def _descrambler(self, taps, bits):
		"""Multiplicative, self-synchronizing scrambler"""
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

	def _crc_ccitt_update(self, crc, data):
		assert data >= 0
		assert data < 0x100
		assert crc >= 0
		assert crc <= 0x10000

		data ^= crc & 0xff
		data ^= (data << 4) & 0xff

		return ((data << 8) | (crc >> 8)) ^ (data >> 4) ^ (data << 3)

	def _check_crc(self, nibbles):
		if len(nibbles) != 84:
			raise InvalidPacket("Wrong length: %d" % len(nibbles))

		crc = 0xffff
		for i in xrange(0, 82, 2):
			crc = self._crc_ccitt_update(crc, nibbles[i] * 0x10 + nibbles[i+1])

		if crc != self.CRC:
			raise InvalidPacket("CRC mismatch: %d != %d" % (crc, self.CRC))

	def _unpack_int(self, nibbles):
		i = 0
		for nibble in nibbles:
			i = (i * 0x10) + nibble

		return i

	def _decode_packet(self, nibbles):

		start_mark		= self._unpack_int(	nibbles[ 0: 1])
		if start_mark != 0x9:
			raise InvalidPacket("Unknown start mark: 0x%x (please report this)" % (start_mark,))

		self.id			= self._unpack_int(	nibbles[ 1: 5])
		time_total_low 		= 			nibbles[ 5: 9]
		pad_1			= self._unpack_int(	nibbles[ 9:13])
		time_on_low		= 			nibbles[13:17]
		pad_2 			= self._unpack_int(	nibbles[17:24])
		energy_low		= 			nibbles[24:31]
		self.power_current	= self._unpack_int(	nibbles[31:35]) / 10.0
		self.power_max		= self._unpack_int(	nibbles[35:39]) / 10.0
		# unknown? (seems to be used for internal calculations)
		self.energy_2		= self._unpack_int(	nibbles[39:45])
		# 						nibbles[45:59]
		time_total_high		=			nibbles[59:62]
		pad_3			= self._unpack_int(	nibbles[62:67])
		energy_high		=			nibbles[67:71]
		time_on_high		=			nibbles[71:74]
		self.reset_counter	= self._unpack_int(	nibbles[74:76])
		flags			= self._unpack_int(	nibbles[76:77])
		pad_4			= self._unpack_int(	nibbles[77:78])
		# crc			= self._unpack_int(	nibbles[78:82])

		# We don't really care about the end mark, or whether it got
		# corrupted, since it's not covered by the CRC check.

		#end_mark		= self._unpack_int(	nibbles[82:84])
		#if end_mark != 0x7e:
		#	raise InvalidPacket("Invalid end mark: %d" % (end_mark,))

		if pad_1 != 0:
			raise InvalidPacket("Padding 1 not zero: 0x%x (please report this)" % (pad_1,))
		if pad_2 != 0:
			raise InvalidPacket("Padding 2 not zero: 0x%x (please report this)" % (pad_2,))
		if pad_3 != 0:
			raise InvalidPacket("Padding 3 not zero: 0x%x (please report this)" % (pad_3,))
		if pad_4 != 0:
			raise InvalidPacket("Padding 4 not zero: 0x%x (please report this)" % (pad_4,))

		self.timestamp		= time.time()

		self.time_total	= self._unpack_int(time_total_high + time_total_low)
		self.time_on	= self._unpack_int(time_on_high + time_on_low)

		self.energy	= self._unpack_int(energy_high + energy_low)

		if flags == 0x8:
			self.device_on_flag = True
		elif flags == 0x0:
			self.device_on_flag = False
		else:
			raise InvalidPacket("Unknown flag value: 0x%x (please report this)" % (flags,))

		# Set properties for compatibility with older ec3k module versions
		self.uptime = self.time_total
		self.since_reset = self.time_on
		self.energy_1 = self.energy
		self.current_power = self.power_current
		self.max_power = self.power_max

	def __str__(self):
		if self.device_on_flag:
			flag = '*'
		else:
			flag = ' '

		return	("id              : %04x\n"
			"time total      : %d seconds\n"
			"time on %s       : %d seconds\n"
			"energy %s        : %d Ws\n"
			"power current   : %.1f W\n"
			"power max       : %.1f W\n"
			"reset counter   : %d") % (
					self.id,
					self.time_total,
					flag, self.time_on,
					flag, self.energy,
					self.power_current,
					self.power_max,
					self.reset_counter)

class EnergyCount3K:
	"""Object representing EnergyCount 3000 receiver"""
	def __init__(self, id=None, callback=None, freq=868.402e6, device=0, osmosdr_args=None):
		"""Create a new EnergyCount3K object

		Takes the following optional keyword arguments:
		id -- ID of the device to monitor
		callback -- callable to call for each received packet
		freq -- central frequency of the channel on which to listen for
		updates (default is known to work for European devices)
		device -- rtl-sdr device to use
		osmosdr_args -- any additional OsmoSDR arguments (e.g. "offset_tune=1")

		If ID is None, then packets for all devices will be received.

		callback should be a function of a callable object that takes
		one EnergyCount3KState object as its argument.
		"""
		self.id = id
		self.callback = callback
		self.freq = freq
		self.device = device
		self.osmosdr_args = osmosdr_args

		self.want_stop = True
		self.state = None
		self.noise_level = -90

	def start(self):
		"""Start the receiver"""
		assert self.want_stop

		self.want_stop = False
		self.threads = []

		self._start_capture()

		capture_thread = threading.Thread(target=self._capture_thread)
		capture_thread.start()
		self.threads.append(capture_thread)

		self._setup_top_block()
		self.tb.start()

	def stop(self):
		"""Stop the receiver and clean up"""
		assert not self.want_stop

		self.want_stop = True

		for thread in self.threads:
			thread.join()

		self.tb.stop()
		self.tb.wait()

		self._clean_capture()

	def get(self):
		"""Get the last received state

		Returns data from the last received packet as a 
		EnergyCount3KState object.
		"""
		return self.state

	def _log(self, msg):
		"""Override this method to capture debug information"""
		pass

	def _start_capture(self):
		self.tempdir = tempfile.mkdtemp()
		self.pipe = os.path.join(self.tempdir, "ec3k.pipe")
		os.mkfifo(self.pipe)

		self.capture_process = None

		try:
			for program in ["capture", "capture.py"]:
				fpath = which(program)
				if fpath is not None:
					self.capture_process = subprocess.Popen(
						[fpath, "-f", self.pipe],
						bufsize=1,
						stdout=subprocess.PIPE)
					return

			raise Exception("Can't find capture binary in PATH")
		except:
			self._clean_capture()
			raise

	def _clean_capture(self):
		if self.capture_process:
			self.capture_process.send_signal(signal.SIGTERM)
			self.capture_process.wait()
			self.capture_process = None

		os.unlink(self.pipe)
		os.rmdir(self.tempdir)

	def _capture_thread(self):

		while not self.want_stop:

			rlist, wlist, xlist = select.select([self.capture_process.stdout], [], [], 1)
			if rlist:
				line = rlist[0].readline()
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

		# Radio receiver, initial downsampling
		args = "rtl=%d,buffers=16" % (self.device,)
		if self.osmosdr_args:
			args += ",%s" % (self.osmosdr_args,)

		osmosdr_source = osmosdr.source(args=args)
		osmosdr_source.set_sample_rate(samp_rate*oversample)
		osmosdr_source.set_center_freq(self.freq, 0)
		osmosdr_source.set_freq_corr(0, 0)
		osmosdr_source.set_gain_mode(1, 0)
		osmosdr_source.set_gain(0, 0)

		taps = filter.firdes.low_pass(1, samp_rate*oversample, 90e3, 8e3,
				filter.firdes.WIN_HAMMING, 6.76)
		low_pass_filter = filter.fir_filter_ccf(oversample, taps)

		self.tb.connect((osmosdr_source, 0), (low_pass_filter, 0))

		# Squelch
		self.noise_probe = analog.probe_avg_mag_sqrd_c(0, 1.0/samp_rate/1e2)
		self.squelch = analog.simple_squelch_cc(self.noise_level, 1)

		noise_probe_thread = threading.Thread(target=self._noise_probe_thread)
		noise_probe_thread.start()
		self.threads.append(noise_probe_thread)

		self.tb.connect((low_pass_filter, 0), (self.noise_probe, 0))
		self.tb.connect((low_pass_filter, 0), (self.squelch, 0))

		# FM demodulation
		quadrature_demod = analog.quadrature_demod_cf(1)

		self.tb.connect((self.squelch, 0), (quadrature_demod, 0))

		# Binary slicing, transformation into capture-compatible format

		add_offset = blocks.add_const_vff((-1e-3, ))

		binary_slicer = digital.binary_slicer_fb()

		char_to_float = blocks.char_to_float(1, 1)

		multiply_const = blocks.multiply_const_vff((255, ))

		float_to_uchar = blocks.float_to_uchar()

		pipe_sink = blocks.file_sink(gr.sizeof_char*1, self.pipe)
		pipe_sink.set_unbuffered(False)

		self.tb.connect((quadrature_demod, 0), (add_offset, 0))
		self.tb.connect((add_offset, 0), (binary_slicer, 0))
		self.tb.connect((binary_slicer, 0), (char_to_float, 0))
		self.tb.connect((char_to_float, 0), (multiply_const, 0))
		self.tb.connect((multiply_const, 0), (float_to_uchar, 0))
		self.tb.connect((float_to_uchar, 0), (pipe_sink, 0))
