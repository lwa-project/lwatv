RaspberryPi
===========
Version of the lwaTV3.py script that runs on the Raspberry Pi Model B (RPi)
and the files necessary to get it running under Raspberry Pi OS.

lwaTV3.rpi.py
-------------
Version of the lwaTV3.py script tuned for the RPi (built using the 
buildRPi.sh script described below).

build2.sh
---------
Script to build lwaTV3.rpi.py, a RPi-compatiable version of lwaTV3.py.

convert3to2.patch
-----------------
Patch file used by buildRPi.sh to tweak the GStreamer video sink.

images
------
Directory containing stock images used by lwaTV3.rpi.py for when images cannot 
be downloaded.

info
----
Directory containing the text image descriptions used by lwaTV3.rpi.py.

movies
------
Directory containing the pre-recorded LWATV movies.  This directory needs
to be populated by a call to updateMovies.py.

setup
-----
Directory containing another README.md file with more information about how
to turn a RPi into a stand alone LWATV display.
