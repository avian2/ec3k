Software receiver for EnergyCount 3000
======================================

This module allows you to receive and decode radio transmissions from
EnergyCount 3000 energy loggers using a RTL-SDR supported radio receiver and
the GNU Radio software defined radio framework.

EnergyCount 3000 transmitters plug between a device and an AC power outlet
and monitor electrical energy usage. They transmit a packet with a status
update every 5 seconds on the 868 MHz SRD band. Reported values include
id of the device, current and maximum seen electrical power, total energy
used and device uptime.


Module content
--------------

The module exports a class that represents the radio receiver. You provide
it with a callback function that is called each time a new status update is
received::

    def callback(state):
    	print state

    my_ec3k = ec3k.EnergyCount3K(callback=callback)

    my_ec3k.start()
    while not want_stop:
    	time.sleep(2)
    	print "Noise level: %.1f dB" % (my_ec3k.noise_level,)

    my_ec3k.stop()

You can also get the last received state by calling the ``get`` method on
the object.

Also included is an example command-line client ``ec3k_recv`` that prints
received packets to standard output.


Requirements
------------

You need the GNU Radio framework, rtl-sdr and the gr-osmosdr package.

http://sdr.osmocom.org/trac/wiki/rtl-sdr

For baseband decoding a pure Python implementation is included in this
package (``capture.py``) and should work out of the box.

For more efficient decoding a C implementation can also be used. Obtain
the source from the address below, compile it and make sure ``capture``
binary is in PATH. It should then get used automatically instead of the
Python implementation.

http://www.tablix.org/~avian/blog/articles/am433/


Known problems
--------------

Occasionally the GNU Radio pipeline isn't setup correctly. If this happens
the noise level constantly stays at -90 dB and no packets are ever
received. Restarting the program usually helps. It's probably a bug in
gr-osmosdr or rtl-sdr.

Stopping the receiver sometimes causes a segfault.

Only half of the data from the EnergyCounter 3000 is decoded. The meaning
of the rest of the bits is currently unknown.

No CRC or data integrity checks are performed on received packets, which
sometimes means the receiver will report bogus readings.


Feedback
--------

Please send patches or bug reports to <tomaz.solc@tablix.org>


Source
------

You can get a local copy of the development repository with::

    git clone git://github.com/avian2/ec3k.git


License
-------

ec3k, software receiver for EnergyCount 3000

Copyright (C) 2012  Tomaz Solc <tomaz.solc@tablix.org>

Copyright (C) 2012  Gasper Zejn

Protocol reverse engineering: http://forum.jeelabs.net/comment/4020

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

..
    vim: set filetype=rst:
