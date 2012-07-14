#!/usr/bin/env python
##################################################
# Gnuradio Python Flow Graph
# Title: Top Block
# Generated: Sat Jul 14 13:33:33 2012
##################################################

from gnuradio import digital
from gnuradio import gr
from gnuradio.eng_option import eng_option
from gnuradio.gr import firdes
from optparse import OptionParser
import math
import osmosdr
import subprocess
import threading
import time

class EnergyCount3KState:
	def __init__(self):
		pass

class EnergyCount3K:
	def __init__(self, id=None, callback=None):
		"""Create a new EnergyCount3K object

		id: ID of the device to monitor
		callback: optional callable to call on each update
		"""
		self.callback = callback
		self.want_stop = True

	def start(self):
		"""Start the receiver
		"""
		assert self.want_stop

		self.want_stop = False
		self.threads = []

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

		for thread in threads:
			thread.join()

	def get(self):
		"""Get the last received state
		"""
		pass

	def _capture_thread(self):
		p = subprocess.Popen(
				["/home/avian/dev/ec3k/am433-0.0.4/am433/capture",
				"-f", "ec3k.pipe" ],
				bufsize=1,
				stdout=subprocess.PIPE)

		while not self.want_stop:
			print p.stdout.readline()

	def _power_probe_thread(self):
		while not self.want_stop:
			power = self.power_probe.level()

			db = 10 * math.log10(max(1e-9, power))
			print "Current noise level: %.1f dB" % (db,)

			self.squelch.set_threshold(db+7.0)
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
		self.power_probe = gr.probe_avg_mag_sqrd_c(0, 1.0/samp_rate/1e2)
		self.squelch = gr.simple_squelch_cc(-90, 1)

		power_probe_thread = threading.Thread(target=self._power_probe_thread)
		power_probe_thread.start()
		self.threads.append(power_probe_thread)

		self.tb.connect((low_pass_filter, 0), (self.power_probe, 0))
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

		pipe_sink = gr.file_sink(gr.sizeof_char*1, "ec3k.pipe")
		pipe_sink.set_unbuffered(False)

		self.tb.connect((quadrature_demod, 0), (add_offset, 0))
		self.tb.connect((add_offset, 0), (binary_slicer, 0))
		self.tb.connect((binary_slicer, 0), (char_to_float, 0))
		self.tb.connect((char_to_float, 0), (multiply_const, 0))
		self.tb.connect((multiply_const, 0), (float_to_uchar, 0))
		self.tb.connect((float_to_uchar, 0), (pipe_sink, 0))

if __name__ == '__main__':
	parser = OptionParser(option_class=eng_option, usage="%prog: [options]")
	(options, args) = parser.parse_args()

	ec3k = EnergyCount3K()

	ec3k.start()

	while True:
		time.sleep(1)

	ec3k.stop()
