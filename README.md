LWATV
=====
Software for displaying LWATV images and movies outside of a web browser.

![Example LWATV GUI window](https://github.com/lwa-project/lwatv/raw/main/images/example.png)

lwaTV3.py
---------
Python script for displaying a GUI showing the latest LWATV image.  The GUI
consists of four parts:
  1) The latest LWATV image,
  2) a picture of the LWA1 site with the VLA in the background, 
  3) an optional pre-recorded LWATV movie for previous days, and
  4) a text description describing what sources are in the images and 
     movies.

This script uses Tkinter (from the Python standard library), the Python
Imaging Library (PIL/Pillow, including the `ImageTk` module), and GStreamer
1.0 for generating the GUI and displaying the images.

On Debian-based systems (including Raspberry Pi OS) `ImageTk` ships in a
separate package from the rest of PIL and must be installed explicitly:

```
sudo apt install python3-pil.imagetk
```

updateMovies.py
---------------
Script to update the on-disk cache of pre-recorded LWATV movies.

images
------
Directory containing stock images used by `lwaTV3.py` for when images cannot 
be downloaded.

info
----
Directory containing the text image descriptions used by `lwaTV3.py`.

movies
------
Directory containing the pre-recorded LWATV movies.  This directory needs
to be populated by a call to `updateMovies.py`.

RaspberryPi
-----------
Information about running LWATV on a Raspberry Pi to build a stand alone kiosk.


Channels
========
LWATV is broadcast on three channels, one per station: channel 1 (LWA1, the
default), channel 2 (LWA-SV), and channel 4 (LWA-NA).  Both scripts pick a
channel the same way -- no flag for channel 1, `-2` for channel 2, or `-4`
for channel 4.

`updateMovies.py` caches the movies for the selected channel and records the
choice in `movies/channel`.  `lwaTV3.py` shows that channel's live image and
description; instead of repeating the flag you can run it with
`-a`/`--auto-select` to follow whatever channel `updateMovies.py` last
downloaded.  If the GUI and the cached movies disagree, `lwaTV3.py` still
shows the live image but hides the mismatched movie panel.


Other LWA Education and Public Outreach Resources
=================================================
 * [LWATV Channel 1](https://leo.phys.unm.edu/~lwa/lwatv.html) - the sky over LWA1
 * [LWATV Channel 2](https://leo.phys.unm.edu/~lwa/lwatv2.html) - the sky over LWA-SV
 * [LWATV Channel 4](https://leo.phys.unm.edu/~lwa/lwatv4.html) - the sky over LWA-NA
 * [lwa_status](https://github.com/lwa-project/lwa_status) - text-based overview of the LWA stations
 * [The Low Frequency Sky](https://fornax.phys.unm.edu/low-frequency-sky/index.html) - an interactive view of the sky below 100 MHz
 * [The Multi-Wavelength Sky](https://fornax.phys.unm.edu/multi-wavelength-sky/index.html) - compare how the sky looks at a variety of wavelengths
