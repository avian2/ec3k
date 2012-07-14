#!/usr/bin/env python
##################################################
# Gnuradio Python Flow Graph
# Title: Top Block
# Generated: Sat Jul 14 13:33:33 2012
##################################################

from gnuradio import digital
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio import window
from gnuradio.eng_option import eng_option
from gnuradio.gr import firdes
from gnuradio.wxgui import fftsink2
from gnuradio.wxgui import forms
from gnuradio.wxgui import scopesink2
from grc_gnuradio import wxgui as grc_wxgui
from optparse import OptionParser
import math
import osmosdr
import threading
import time
import wx

class top_block(grc_wxgui.top_block_gui):

	def __init__(self):
		grc_wxgui.top_block_gui.__init__(self, title="Top Block")

		##################################################
		# Variables
		##################################################
		self.squelch_level = squelch_level = 0
		self.samp_rate = samp_rate = 96000
		self.freq = freq = 868.388e6

		##################################################
		# Blocks
		##################################################
		self.gr_probe_avg_mag_sqrd_x_0 = gr.probe_avg_mag_sqrd_c(0, 1.0/samp_rate/1e2)
		def _squelch_level_probe():
			while True:
				val = self.gr_probe_avg_mag_sqrd_x_0.level()
				try: self.set_squelch_level(val)
				except AttributeError, e: pass
				time.sleep(1.0/(1))
		_squelch_level_thread = threading.Thread(target=_squelch_level_probe)
		_squelch_level_thread.daemon = True
		_squelch_level_thread.start()
#		self.wxgui_scopesink2_0 = scopesink2.scope_sink_f(
#			self.GetWin(),
#			title="Scope Plot",
#			sample_rate=samp_rate,
#			v_scale=1,
#			v_offset=0.5,
#			t_scale=0.5e-3,
#			ac_couple=False,
#			xy_mode=False,
#			num_inputs=2,
#			trig_mode=gr.gr_TRIG_MODE_NORM,
#			y_axis_label="Counts",
#		)
		#self.Add(self.wxgui_scopesink2_0.win)
#		self.wxgui_fftsink2_0 = fftsink2.fft_sink_c(
#			self.GetWin(),
#			baseband_freq=0,
#			y_per_div=10,
#			y_divs=10,
#			ref_level=0,
#			ref_scale=2.0,
#			sample_rate=samp_rate,
#			fft_size=1024,
#			fft_rate=15,
#			average=False,
#			avg_alpha=None,
#			title="FFT Plot",
#			peak_hold=False,
#		)
#		self.Add(self.wxgui_fftsink2_0.win)
		self.osmosdr_source_c_0 = osmosdr.source_c( args="nchan=" + str(1) + " " + "rtl=0,buffers=16"  )
		self.osmosdr_source_c_0.set_sample_rate(samp_rate*10)
		self.osmosdr_source_c_0.set_center_freq(868.403e6, 0)
		self.osmosdr_source_c_0.set_freq_corr(0, 0)
		self.osmosdr_source_c_0.set_gain_mode(1, 0)
		self.osmosdr_source_c_0.set_gain(0, 0)
		self.low_pass_filter_0 = gr.fir_filter_ccf(10, firdes.low_pass(
			1, samp_rate*10, 90e3, 8e3, firdes.WIN_HAMMING, 6.76))
		self.gr_simple_squelch_cc_0 = gr.simple_squelch_cc(10*math.log10(max(1e-9, squelch_level))+7, 1)
		self.gr_quadrature_demod_cf_0 = gr.quadrature_demod_cf(1)
		self.gr_multiply_const_vxx_0 = gr.multiply_const_vff((255, ))
		self.gr_float_to_uchar_0 = gr.float_to_uchar()
		self.gr_file_sink_0 = gr.file_sink(gr.sizeof_char*1, "ec3k.pipe")
		self.gr_file_sink_0.set_unbuffered(False)
		self.gr_char_to_float_0 = gr.char_to_float(1, 1)
		self.gr_add_const_vxx_0 = gr.add_const_vff((-1e-3, ))
		self._freq_text_box = forms.text_box(
			parent=self.GetWin(),
			value=self.freq,
			callback=self.set_freq,
			label="freq",
			converter=forms.float_converter(),
		)
		self.Add(self._freq_text_box)
		self.digital_binary_slicer_fb_0 = digital.binary_slicer_fb()

		##################################################
		# Connections
		##################################################
		self.connect((self.gr_simple_squelch_cc_0, 0), (self.gr_quadrature_demod_cf_0, 0))
		self.connect((self.digital_binary_slicer_fb_0, 0), (self.gr_char_to_float_0, 0))
		self.connect((self.gr_char_to_float_0, 0), (self.gr_multiply_const_vxx_0, 0))
		self.connect((self.gr_multiply_const_vxx_0, 0), (self.gr_float_to_uchar_0, 0))
		self.connect((self.gr_float_to_uchar_0, 0), (self.gr_file_sink_0, 0))
		self.connect((self.osmosdr_source_c_0, 0), (self.low_pass_filter_0, 0))
		self.connect((self.low_pass_filter_0, 0), (self.gr_simple_squelch_cc_0, 0))
		#self.connect((self.low_pass_filter_0, 0), (self.wxgui_fftsink2_0, 0))
		self.connect((self.low_pass_filter_0, 0), (self.gr_probe_avg_mag_sqrd_x_0, 0))
		self.connect((self.gr_add_const_vxx_0, 0), (self.digital_binary_slicer_fb_0, 0))
		self.connect((self.gr_quadrature_demod_cf_0, 0), (self.gr_add_const_vxx_0, 0))
		#self.connect((self.gr_char_to_float_0, 0), (self.wxgui_scopesink2_0, 0))
		#self.connect((self.gr_quadrature_demod_cf_0, 0), (self.wxgui_scopesink2_0, 1))

	def get_squelch_level(self):
		return self.squelch_level

	def set_squelch_level(self, squelch_level):
		self.squelch_level = squelch_level
		self.gr_simple_squelch_cc_0.set_threshold(10*math.log10(max(1e-9, self.squelch_level))+7)

	def get_samp_rate(self):
		return self.samp_rate

	def set_samp_rate(self, samp_rate):
		self.samp_rate = samp_rate
		self.wxgui_fftsink2_0.set_sample_rate(self.samp_rate)
		self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate*10, 90e3, 8e3, firdes.WIN_HAMMING, 6.76))
		self.osmosdr_source_c_0.set_sample_rate(self.samp_rate*10)
		self.gr_probe_avg_mag_sqrd_x_0.set_alpha(1.0/self.samp_rate/1e2)
		self.wxgui_scopesink2_0.set_sample_rate(self.samp_rate)

	def get_freq(self):
		return self.freq

	def set_freq(self, freq):
		self.freq = freq
		self._freq_text_box.set_value(self.freq)

if __name__ == '__main__':
	parser = OptionParser(option_class=eng_option, usage="%prog: [options]")
	(options, args) = parser.parse_args()
	tb = top_block()
	tb.Run(True)

