RaspberryPi
===========
Running the LWATV GUI on a Raspberry Pi as a stand-alone kiosk display, using
Raspberry Pi OS (Bookworm or Trixie).

As of the Tkinter port the default `lwaTV3.py` in the repository root runs on
the Raspberry Pi without modification, so there is no longer a Pi-specific
build of the script or a patch to maintain -- just run the top-level
`lwaTV3.py` and `updateMovies.py`.

Quick Setup
-----------
 1. Install Raspberry Pi OS with desktop (Bookworm or later) on an 8 GB or
    larger SD card and walk through the first-boot wizard.
 2. Check out the software into your home directory:
    ```
    git clone https://github.com/lwa-project/lwatv.git LWATV
    ```
 3. Run the provisioning script:
    ```
    bash ~/LWATV/RaspberryPi/setup.sh
    ```
    It installs the required packages, populates the movie cache, and installs
    the desktop autostart entry and the daily movie-update cron job.  It is
    safe to re-run later to update the machine.
 4. Set the two display options that cannot be scripted safely:
    * Enable automatic login to the desktop (`raspi-config` -> System
      Options -> Boot / Auto Login).
    * Disable the screensaver so the display does not blank
      (Preferences -> Screensaver).
 5. Reboot, or launch the GUI immediately with:
    ```
    python3 ~/LWATV/lwaTV3.py
    ```

Manual Setup
------------
If you would rather understand the moving parts (or `setup.sh` does not fit
your setup), here is what it does.

 1. Install the following packages via `apt`:

     * git
     * gir1.2-gstreamer-1.0
     * gir1.2-gst-plugins-base-1.0
     * gstreamer1.0-plugins-base
     * gstreamer1.0-plugins-good
     * gstreamer1.0-plugins-bad
     * gstreamer1.0-libav
     * python3
     * python3-gi
     * python3-gst-1.0
     * python3-pil
     * python3-pil.imagetk
     * python3-tk
     * xscreensaver

    `python3-pil.imagetk` is a separate package from `python3-pil` on Debian
    and is required for the GUI to render images.  The `gir1.2-gst*` typelibs
    are what `gi.require_version('Gst', ...)` /
    `gi.require_version('GstVideo', ...)` load at import time, and the
    `gstreamer1.0-plugins-*`/`-libav` packages provide the demux and H.264
    decode for the `.mov` movies.

 2. Populate the movie cache:
    ```
    python3 ~/LWATV/updateMovies.py
    ```
 3. Add a `lwatv.desktop` file into `~/.config/autostart` to launch the GUI
    on login:
    ```
    [Desktop Entry]
    Type=Application
    Name=LWATV GUI
    Comment=The LWATV GUI
    Terminal=false
    StartupNotify=false
    Exec=sh -c "sleep 10 && python3 /home/pi/LWATV/lwaTV3.py"
    ```
 4. Add the following line to your crontab to update the movies every day at
    5:10 local time:
    ```
    10 5 * * * python3 /home/pi/LWATV/updateMovies.py
    ```

Video Sink
----------
The Pi uses playbin's default video sink, which embeds correctly into the GUI
window.  If you ever land on a display stack where the movie does not appear
inside the window, force an X11 sink via the `LWATV_VIDEO_SINK` environment
variable, e.g.:
```
LWATV_VIDEO_SINK=ximagesink python3 ~/LWATV/lwaTV3.py
```
