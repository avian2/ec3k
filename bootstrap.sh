#!/bin/bash

set -e

if [ ! -d "am433" ]; then
	echo "Please run this script at the top directory of the am433 distribution!"
	exit 1
fi

echo "Compiling capture"

(cd am433 && make)

echo "Cloning and compiling libpcap"

git clone http://chandra.tablix.org/~avian/git/libpcap.git
(cd libpcap && ./configure && sleep 1 && make)

echo "Cloning and compiling tcpdump"

git clone http://chandra.tablix.org/~avian/git/tcpdump.git
(cd tcpdump && ./configure && sleep 1 && make)
