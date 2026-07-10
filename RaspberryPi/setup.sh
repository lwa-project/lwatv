#!/bin/bash
#
# Provision a Raspberry Pi (Raspberry Pi OS Bookworm or later) to run the
# LWATV GUI.  Safe to re-run: it installs/updates packages, refreshes the
# movie cache, and (re)installs the autostart entry and movie-update cron job.
#
# Usage, from a checked-out copy of the repository:
#     bash RaspberryPi/setup.sh
#

set -euo pipefail

# Repository root, derived from this script's location so the paths baked into
# the autostart entry and crontab are always correct.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON=/usr/bin/python3
GUI="${REPO_DIR}/lwaTV3.py"
UPDATER="${REPO_DIR}/updateMovies.py"

echo "==> LWATV repository: ${REPO_DIR}"

# 1. Packages -----------------------------------------------------------------
#    * python3-tk / python3-pil / python3-pil.imagetk : the Tkinter GUI and
#      its image rendering (ImageTk is a separate Debian package from PIL).
#    * python3-gi / python3-gst-1.0 and the gir1.2-* typelibs : the PyGObject
#      GStreamer bindings that `gi.require_version('Gst'/'GstVideo', ...)` needs.
#    * gstreamer1.0-plugins-{base,good,bad} + gstreamer1.0-libav : demux and
#      H.264 decode for the .mov movies (qtdemux, h264parse, avdec_h264).
PACKAGES=(
    git
    python3
    python3-gi
    python3-gst-1.0
    gir1.2-gstreamer-1.0
    gir1.2-gst-plugins-base-1.0
    python3-tk
    python3-pil
    python3-pil.imagetk
    gstreamer1.0-plugins-base
    gstreamer1.0-plugins-good
    gstreamer1.0-plugins-bad
    gstreamer1.0-libav
    xscreensaver
)

echo "==> Installing packages"
sudo apt update
sudo apt install -y "${PACKAGES[@]}"

# 2. Movie cache --------------------------------------------------------------
echo "==> Populating the movie cache"
"${PYTHON}" "${UPDATER}"

# 3. Autostart entry ----------------------------------------------------------
echo "==> Installing the desktop autostart entry"
AUTOSTART_DIR="${HOME}/.config/autostart"
mkdir -p "${AUTOSTART_DIR}"
cat > "${AUTOSTART_DIR}/lwatv.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=LWATV GUI
Comment=The LWATV GUI
Terminal=false
StartupNotify=false
Exec=sh -c "sleep 10 && ${PYTHON} ${GUI}"
EOF

# 4. Daily movie-update cron job (idempotent) ---------------------------------
echo "==> Installing the daily movie-update cron job"
CRON_LINE="10 5 * * * ${PYTHON} ${UPDATER}"
# Drop any prior LWATV updater line, then add the current one back.
( crontab -l 2>/dev/null | grep -vF "${UPDATER}" ; echo "${CRON_LINE}" ) | crontab -

cat <<EOF

==> Done.

Two things still need to be set once, by hand, to run as a dedicated display:
  * Enable automatic login to the desktop (raspi-config -> System Options).
  * Disable the screensaver (Preferences -> Screensaver), so the display does
    not blank.

Launch the GUI now without rebooting with:
    ${PYTHON} ${GUI}
EOF
