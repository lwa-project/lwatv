LWATV
=====
Software for displaying LWATV images and movies outside of a web broswer.

lwaTV3.py
---------
Python script for displaying a GUI showing the latest LWATV image.  The GUI
consists of four parts:
  1) The latest LWATV image (or where the beams are pointed if PASI isn't 
     running), 
  2) a picture of the LWA1 site with the VLA in the background, 
  3) an optional pre-recorded LWATV movie for previous days, and
  4) a text description describing what sources are in the images and 
     movies.

This script uses wxPython and GStreamer 1.0 for generating the GUI and 
displaying the images.

lwaTV2.py
---------
Version of the lwaTV3.py script for GStreamer 0.10 installs (built using 
the build2.sh script described below).

updateMovies.py
---------------
Script to update the on-disk cache of pre-recorded LWATV movies.

build2.sh
---------
Script to build lwaTV2.py, a GStreamer 0.10-compatiable version of 
lwaTV3.py.

convert3to2.patch
-----------------
Patch file used by build2.sh to convert from GStreamer 1.0 to 0.10.

images
------
Directory containing stock images used by lwaTV3.py for when images cannot 
be downloaded.

info
----
Directory containing the text image descriptions used by lwaTV3.py.

movies
------
Directory containing the pre-recorded LWATV movies.  This directory needs
to be populated by a call to updateMovies.py.

RaspberryPi
-----------
Raspberry Pi-specific version of lwaTV3.py.
