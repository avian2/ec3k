#!/usr/bin/python

from distutils.core import Command, setup
import unittest

UNITTESTS = [
		"tests", 
	]

class TestCommand(Command):
	user_options = [ ]

	def initialize_options(self):
		pass

	def finalize_options(self):
		pass

	def run(self):
		suite = unittest.TestSuite()

		suite.addTests( 
			unittest.defaultTestLoader.loadTestsFromNames( 
								UNITTESTS ) )

		result = unittest.TextTestRunner(verbosity=2).run(suite)

setup(name='ec3k',
	version='1.0.0',
	description='Use rtl-sdr to receive EnergyCount 3000 transmissions.',
	license='GPLv3',
	long_description=open("README.rst").read(),
	author='Tomaz Solc',
	author_email='tomaz.solc@tablix.org',

	py_modules = ['ec3k'],
	scripts = ['ec3k_recv', 'capture.py'],
	provides = [ 'ec3k' ],

	cmdclass = { 'test': TestCommand }
)
