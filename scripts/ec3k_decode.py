import itertools
import sys

class InvalidPacket(Exception): pass

# unpacks hex printed data into individual bits
def get_bits(hex_bytes):
	bits = []

	for hex_byte in hex_bytes:
		i = int(hex_byte, 16)
		for n in xrange(8):
			bits.append(bool((i<<n) & 0x80))

	return bits

# shift bits into bytes, msb first
def get_bytes(bits):
	bytes = [0] * (len(bits)/8+1)
	for n, bit in enumerate(bits):
		bytes[n/8] |= (int(bit) << (7-n%8))

	return bytes

# wierd bit shuffling operation required?
def bit_shuffle(bits):
	nbits = []

	# first, invert byte bit order 
	args = [iter(bits)] * 8
	for bit_group in itertools.izip_longest(fillvalue=False, *args):
		nbits += reversed(bit_group)

	# add 4 zero bits at the start
	nbits = [False]*4 + nbits

	return nbits

# multiplicative, self-synchronizing scrambler
def descrambler(taps, bits):
	nbits = []

	state = [ False ] * max(taps)

	for bit in bits:

		out = bit
		for tap in taps:
			out = out ^ state[tap-1]
		nbits.append(out)

		state = [ bit ] + state[:-1]

	return nbits

# non-return-to-zero-space decoder
def nrzs_decode(bits):
	nbits = []

	p = True
	for bit in bits:
		if bool(bit) == bool(p):
			nbits.append(True)
		else:
			nbits.append(False)
		p = bit

	return nbits

# bit stuffing reversal.
#
# 6 consecutive 1s serve as a packet start/stop condition
#
# in the packet, one zero is stuffed after 5 consecutive 1s
def bit_unstuff(bits):
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
				raise InvalidPacket

			cnt = 0

	return nbits

def unpack_int(bytes):
	i = 0
	for byte in bytes:
		i = (i * 0x100) + byte

	return i

def print_packet(bytes):

	print "   ",
	for n in xrange(16):
		print "%2x" % n,

	for n, byte in enumerate(bytes):
		if not (n%16):
			print
			print "%02x " % n,
		print "%02x" % byte,
	print

	id		= unpack_int(bytes[1:3])
	uptime		= unpack_int(bytes[3:5])
	since_reset	= unpack_int(bytes[5:9])
	energy_1	= unpack_int(bytes[9:16])
	current_power	= unpack_int(bytes[16:18])/10.0
	max_power	= unpack_int(bytes[18:20])/10.0
	energy_2	= unpack_int(bytes[20:23])

	print
	print "id              : %04x" % id
	print "uptime          : %d seconds" % uptime 
	print "since last reset: %d seconds" % since_reset
	print "energy          : %d Ws" % energy_1
	print "current power   : %.1f W" % current_power
	print "max power       : %.1f W" % max_power
	print "energy          : %d Ws" % energy_2
	print


def main():
	# open a log of the capture process, text format
	for line in open(sys.argv[1]):
		fl = line.split()
		if fl and fl[0] == "data":
			bits = get_bits(fl[1:])
			bits = [ not bit for bit in bits ]

			bits = descrambler([18, 17, 13, 12, 1], bits)
			bits = [ not bit for bit in bits ]
			
			#print bits

			try:
				bits = bit_unstuff(bits)
			except InvalidPacket:
				print "Invalid packet"
				continue

			bits = bit_shuffle(bits)
			
			bytes = get_bytes(bits)
			print_packet(bytes)


			#print bits[0:16]
			#print len(bits)

main()
