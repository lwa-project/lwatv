Setting Up the LWATV GUI on Raspbian
====================================

 1. Install Raspberry Pi OS with desktop (Buster or later) on a 8 GB or larger SD card.
 2. Boot the RPi and walk through the setup wizard.
 3. Install the following extra packages via `apt-get`:
 
  * git
  * python3
  * python3-wxgtk4.0
  * python3-pip
  * python3-gi
  * python3-git
  * python3-gst-1.0
  * gstreamer1.0-plugins-good
  * gstreamer1.0-omx
  * gstreamer1.0-omx-rpi
  * xscreensaver
  
 4. Checkout the LWATV GUI software from github.com into the home directory via: `git clone https://github.com/lwa-project/lwatv.git LWATV`
 5. Launch the GUI with: `python3 /home/pi/LWATV/RaspberryPi/lwaTV3.rpi.py`
