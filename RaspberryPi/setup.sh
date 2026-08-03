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

# The script uses `sudo` internally for the privileged steps (apt, systemctl),
# but the movie cache, autostart entry, and crontab are all per-user and must
# belong to the person setting up the display -- not root.  When the whole
# script is launched with `sudo`, `${USER}`/`${HOME}` point at root, so resolve
# the real invoking user from `${SUDO_USER}` and look their home up in passwd
# (rather than trusting `${HOME}`, which sudo has already reset to /root).
TARGET_USER="${SUDO_USER:-$(id -un)}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"

# Run a command as the invoking user.  When already running as that user this
# is a plain exec; only when we are root (script run under sudo) do we drop
# privileges back down with `sudo -u`.
run_as_user() {
    if [ "$(id -u)" -eq 0 ] && [ "${TARGET_USER}" != "root" ]; then
        sudo -u "${TARGET_USER}" "$@"
    else
        "$@"
    fi
}

echo "==> LWATV repository: ${REPO_DIR}"
echo "==> Configuring for user: ${TARGET_USER} (${TARGET_HOME})"

# 1. Packages -----------------------------------------------------------------
#    * python3-tk / python3-pil / python3-pil.imagetk : the Tkinter GUI and
#      its image rendering (ImageTk is a separate Debian package from PIL).
#    * python3-gi / python3-gst-1.0 and the gir1.2-* typelibs : the PyGObject
#      GStreamer bindings that `gi.require_version('Gst'/'GstVideo', ...)` needs.
#    * gstreamer1.0-plugins-{base,good,bad} + gstreamer1.0-libav : demux and
#      H.264 decode for the .mov movies (qtdemux, h264parse, avdec_h264).
PACKAGES=(
    git
    cron
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
#    Run as the invoking user so the cached .mov files (and the `channel` file
#    the GUI rewrites) are owned by them -- not root -- otherwise the daily
#    cron job and the GUI could never update the cache afterward.
echo "==> Populating the movie cache"
run_as_user "${PYTHON}" "${UPDATER}"

# 3. Autostart entry ----------------------------------------------------------
echo "==> Installing the desktop autostart entry"
AUTOSTART_DIR="${TARGET_HOME}/.config/autostart"
run_as_user mkdir -p "${AUTOSTART_DIR}"
run_as_user tee "${AUTOSTART_DIR}/lwatv.desktop" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Name=LWATV GUI
Comment=The LWATV GUI
Terminal=false
StartupNotify=false
Exec=sh -c "sleep 10 && ${PYTHON} ${GUI} -a"
EOF

# 4. Daily movie-update cron job (idempotent) ---------------------------------
echo "==> Installing the daily movie-update cron job"
# Make sure the cron daemon is installed (see PACKAGES) and actually running,
# otherwise the crontab entry below would be installed but never fire.
sudo systemctl enable --now cron
CRON_LINE="10 5 * * * ${PYTHON} ${UPDATER}"
# Drop any prior LWATV updater line, then add the current one back, all against
# the invoking user's crontab (not root's).  The `|| true` keeps `grep` from
# aborting the script (under `set -e`/`pipefail`) when it selects no lines,
# e.g. on a fresh system with an empty crontab.
( run_as_user crontab -l 2>/dev/null | grep -vF "${UPDATER}" || true ; echo "${CRON_LINE}" ) | run_as_user crontab -

cat <<EOF

==> Done.

Two things still need to be set once, by hand, to run as a dedicated display:
  * Enable automatic login to the desktop (raspi-config -> System Options).
  * Disable the screensaver (Preferences -> Screensaver), so the display does
    not blank.

Launch the GUI now without rebooting with:
    ${PYTHON} ${GUI} -a
EOF
