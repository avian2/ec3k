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


Dependencies
------------

You need the GNU Radio framework, rtl-sdr and the gr-osmosdr package.

http://sdr.osmocom.org/trac/wiki/rtl-sdr

For baseband decoding a pure Python implementation is included in this
package (``capture.py``).

For more efficient decoding the C implementation can also be used. Obtain
the source from the address below and make sure ``capture`` binary is in
PATH:

http://www.tablix.org/~avian/blog/articles/am433/


Source
------

You can get a local copy of the development repository with::

    git clone git://github.com/avian2/ec3k.git

..
    vim: set filetype=rst:
