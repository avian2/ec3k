import ec3k
import unittest

class TestEnergyCount3KState(unittest.TestCase):
	def test_basic(self):
		hex_bytes = ['ca', 'ff', '9c', 'e0', '66', '10', '34', '6d', '3a', '83', '53', '12', 'fe', 'c0', 'f5', '09', '4c', '76', '07', '3d', '16', '29', '96', '8f', '75', '1d', '93', '7e', '54', 'cf', '1e', 'c2', '36', '17', '2f', '2c', '0e', '12', 'cd', '8f', '14', '8e', '77', '1e', 'f1', 'ca', 'ce', 'e3', '23', 'e9', '05', 'ce', '74', 'aa', 'da', '52', '62', 'a5', 'b1', 'a3', '58', '4e', 'bd', 'ae', 'c4', '77', 'e9', '89', 'a0']

		state = ec3k.EnergyCount3KState(hex_bytes)

		self.assertEqual(state.id, 0xf100)
		self.assertEqual(state.uptime, 36725)
		self.assertEqual(state.since_reset, 6006)
		self.assertEqual(state.energy_1, 138854)
		self.assertEqual(state.current_power, 0)
		self.assertEqual(state.max_power, 86.8)
		self.assertEqual(state.energy_2, 2221664)
