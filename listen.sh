#!/bin/bash

CARDN=`arecord -l|sed -ne '/^card /{s/:.*//;s/.* //;h};${g;p}'`
DEV="hw:$CARDN,0"
echo "Listening device $DEV"
gst-launch alsasrc device=$DEV ! alsasink
