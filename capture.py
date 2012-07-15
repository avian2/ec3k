#!/usr/bin/python
"""Software receiver for EnergyCount 3000
Copyright (C) 2012  Gasper Zejn

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

import sys
import os

BUFFSIZE = 4096
MOD_UNKNOWN = 2
MOD_BINARY  = 5

MIN_BREAK = 100

class Packet:
	TRIM = 10
	expected_bit_size = 4
	
	def __init__(self):
		self.data = []
		self.len = 0
		self.start = -1
		self.ntran = 0
		self.breaklen = 0
		
		self.decoded = ''
		self.bitcount = 0
		self.cp = 0
		self.modulation = MOD_UNKNOWN
		
		self.leader_edges = 0
		self.trailer_edges = 0
		self.bits = 0
	
	def __repr__(self):
		return 'Packet: len=%s ntran=%s' % (len(self.data), self.ntran)
	
	def push_bit(self, val):
		assert val in (1,0)
		self.bits = self.bits << 1 | val
	
	def trim(self, data):
		
		if len(data) < 10:
			return []
		
		if len(set(data[:self.expected_bit_size])) == 1:
			# start is ok
			start = 0
		else:
			# remove grass
			start = self.expected_bit_size
			for i in [3,2,1]:
				if data[start] == data[i]:
					start = i
				else:
					break
		
		if len(set(data[-self.expected_bit_size:])) == 1:
			end = 0
		else:
			end = self.expected_bit_size
			for i in [3,2,1]:
				if data[-end] == data[-i]:
					end = i
				else:
					break
		if start:
			data = data[start:]
		if end:
			data = data[:-end]
		return data
	
	def old_trim(self, data):
		start = self.TRIM
		for i, v in enumerate(data):
			if i < start:
				pv = v
				continue
			if pv == v:
				start = i+1
			else:
				break
		
		stop = self.TRIM
		for i, v in enumerate(reversed(data)):
			if i < stop:
				pv = v
				continue
			if pv == v:
				stop = i + 1
			else:
				break
		return data[start:-stop]
	
	def recover_clock(self):
		cp = None
		
		#print ''.join([str(i) for i in self.data]).replace('0', '.')
		print ''.join([str(i) for i in self.trim(self.data)]).replace('0', '.')
		
		if len(self.data) < 50:
			return False
		
		pt = 0
		# find shortest pulse length in packet
		for tt, v in enumerate(self.trim(self.data)):
			if tt == 0:
				pv = v
			t = tt+1
			if pv != v:
				pl = t - pt
				#print pl, 'from', pt, 'to', t, pv, '->', v
				if pl < 2:
					print >> sys.stderr, 'pulse too short', pl
					return False
				if cp is None:
					cp = pl
				if pl < cp:
					cp = pl
				pv = v
				pt = t
		
		if cp is None:
			return False
		
		cp = float(cp)
		#print 'cp estimate = %s' % cp
		v = self.data[0]
		# adjust clock
		pt = 0
		for tt, v in enumerate(self.trim(self.data)):
			if tt == 0:
				pv = v
			t = tt+1
			if pv != v:
				pl = t - pt
				if (pl < cp):
					cp = (cp*2.0 + pl) / 3.0
				elif pl > cp:
					r = pl / cp
					#print pl, cp
					n = round(r)
					e = abs((r-n)/n)
					if e > 0.4:
						#print e
						print >> sys.stderr, 'inconsistent pulse length'
						return False
					if n > 20:
						print >> sys.stderr, 'too many consecutive same bits'
						return False
					cp = (cp*2.0 + pl/n) / 3.0
				pv = v
				pt = t
		
		#print 'cp got = %s' % cp
		# decode bits
		pt = 0
		for tt, v in enumerate(self.trim(self.data)):
			if tt == 0:
				pv = v
			t = tt+1
			if pv != v:
				pl = t - pt
				
				r = pl / cp
				nbits = int(round(r))
				
				for n in xrange(nbits):
					self.push_bit(pv)
				pv = v
				pt = t
		
		hd = iter('%x' % self.bits)
		h = ' '.join(['%s%s' % i for i in zip(hd, hd)])
		print 'data ', h

class Packetizer:
	
	def __init__(self):
		self.sample_cnt = 0
		self.pv = 0
		self.packet = None
		self.data = ""
	
	def feed(self, data):
		self.data = self.data + data
		
		for packet in self._nextpacket():
			yield packet
	
	def _nextpacket(self):
		datalen = len(self.data)
		i = 0
		
		if self.packet is None:
			self.packet = Packet()
		
		packet = self.packet
		inpacket = bool(packet.data)
		breaklen = 0
		
		while i < datalen:
			v = ord(self.data[i]) >= 190 and 1 or 0
			
			if v != self.pv:
				inpacket = True
				self.pv = v
				packet.ntran += 1
				# breaklen XXX
				breaklen = 0
			else:
				breaklen += 1
			
			if inpacket:
				packet.data.append(v)
				# ce je break
				if breaklen > MIN_BREAK:
					# trim break and return packet
					packet.data = packet.data[:len(packet.data)-breaklen]
					if packet.data:
						packet.data = packet.data[:-1]
					if packet.data:
						yield packet
					self.packet = packet = Packet()
					inpacket = False
			
			i += 1
		self.data = ''
		

def run_loop(fd):
	
	packetizer = Packetizer()

	data = fd.read(BUFFSIZE)
	readlen = len(data)
	while readlen > 0:
		
		# packetizer
		for packet in packetizer.feed(data):
			packet.recover_clock()
			#print packet
		
		data = fd.read(BUFFSIZE)
		readlen = len(data)
	
	
	
	
	
	
	
	

if __name__ == "__main__":
	try:
		fd = open(sys.argv[2])
	except IndexError:
		fd = sys.stdin
	run_loop(fd)
