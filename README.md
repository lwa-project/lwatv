LWATV
=====
Software for displaying LWATV images and movies outside of a web broswer.

![Example LWATV GUI window](https://github.com/lwa-project/lwatv/raw/main/images/example.png)

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

updateMovies.py
---------------
Script to update the on-disk cache of pre-recorded LWATV movies.

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


Other LWA Education and Public Outreach Resources
=================================================
 * [lwa_status](https://github.com/lwa-project/lwa_status) - text-based overview of the LWA stations
 * [The Low Frequency Sky](https://fornax.phys.unm.edu/low-frequency-sky/index.html) - an interactive view of the sky below 100 MHz
 * [The Multi-Wavelength Sky](https://fornax.phys.unm.edu/multi-wavelength-sky/index.html) - compare how the sky looks at a variety of wavelengths
