RaspberryPi
===========
Notes and helper files for running the LWATV GUI on a Raspberry Pi as a
stand-alone kiosk display, using Raspberry Pi OS.

As of the Tkinter port the default `lwaTV3.py` in the repository root runs on
the Raspberry Pi without modification, so there is no longer a Pi-specific
build of the script or a patch to maintain -- just run the top-level
`lwaTV3.py` and `updateMovies.py`.

setup
-----
Directory containing `setup.sh`, a script that provisions a fresh Raspberry
Pi OS install to run the GUI (packages, movie cache, desktop autostart entry,
and the daily movie-update cron job), plus a `README.md` documenting both the
scripted and the manual setup steps.
