#!/bin/bash
# Bring up the local X desktop that dockerless mode drives.
#
# InfantAgent normally gets its desktop from a systemd/GNOME container. Where
# containers cannot be created (no CAP_SYS_ADMIN, namespaces blocked by
# seccomp) this provides the same thing out of plain user-space processes:
#
#   Xvfb :10          virtual framebuffer, no GPU or /dev/tty needed
#   openbox           window manager, so windows get decorations and focus
#   x11vnc            exposes :10 over VNC on 127.0.0.1
#   websockify/noVNC  serves that VNC stream as a web page
#
# The agent itself does not use VNC -- it drives the display with xdotool and
# grabs frames with PIL, both over a local shell. VNC is only so a human can
# watch. Idempotent: re-running only starts what is not already up.

set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-:10}"
GEOMETRY="${GEOMETRY:-1920x1080x24}"
VNC_PORT="${VNC_PORT:-5910}"
NOVNC_PORT="${INFANT_NOVNC_PORT:-6080}"
LOG_DIR="${LOG_DIR:-/tmp/infant-desktop}"

mkdir -p "$LOG_DIR"

running() { pgrep -f "$1" >/dev/null 2>&1; }

# --- Xvfb ---------------------------------------------------------------
if xdpyinfo -display "$DISPLAY_NUM" >/dev/null 2>&1; then
    echo "Xvfb        already on $DISPLAY_NUM"
else
    echo "Xvfb        starting on $DISPLAY_NUM ($GEOMETRY)"
    nohup Xvfb "$DISPLAY_NUM" -screen 0 "$GEOMETRY" \
        -ac +extension GLX +extension RANDR +render -noreset \
        >"$LOG_DIR/xvfb.log" 2>&1 &
    for _ in $(seq 1 40); do
        xdpyinfo -display "$DISPLAY_NUM" >/dev/null 2>&1 && break
        sleep 0.5
    done
    xdpyinfo -display "$DISPLAY_NUM" >/dev/null 2>&1 \
        || { echo "Xvfb failed to start; see $LOG_DIR/xvfb.log" >&2; exit 1; }
fi

export DISPLAY="$DISPLAY_NUM"

# --- window manager -----------------------------------------------------
if running "^openbox"; then
    echo "openbox     already running"
else
    echo "openbox     starting"
    nohup openbox >"$LOG_DIR/openbox.log" 2>&1 &
    sleep 1
fi

# --- x11vnc / noVNC -----------------------------------------------------
# Only a human viewer needs these. The agent drives the display with xdotool
# and grabs frames with PIL, both locally, so with NO_VNC=1 everything above is
# still enough for it to work -- useful when the ports cannot be reached anyway.
if [ "${NO_VNC:-0}" = 1 ]; then
    echo "x11vnc      skipped (NO_VNC=1)"
    echo "noVNC       skipped (NO_VNC=1)"
    echo
    echo "Desktop ready on $DISPLAY_NUM (headless: no viewer)"
    echo "Logs: $LOG_DIR"
    exit 0
fi

if running "x11vnc .*-rfbport $VNC_PORT"; then
    echo "x11vnc      already on $VNC_PORT"
else
    echo "x11vnc      starting on 127.0.0.1:$VNC_PORT"
    nohup x11vnc -display "$DISPLAY_NUM" -forever -shared -nopw \
        -rfbport "$VNC_PORT" -localhost -quiet \
        >"$LOG_DIR/x11vnc.log" 2>&1 &
    sleep 1
fi

# --- noVNC --------------------------------------------------------------
if running "websockify .*$NOVNC_PORT"; then
    echo "noVNC       already on $NOVNC_PORT"
else
    echo "noVNC       starting on $NOVNC_PORT"
    nohup websockify --web=/usr/share/novnc "$NOVNC_PORT" \
        "localhost:$VNC_PORT" >"$LOG_DIR/novnc.log" 2>&1 &
    sleep 2
fi

# --- make it look alive ------------------------------------------------
# An empty openbox root window is pure black, which is indistinguishable from
# "the desktop failed to start". Paint the root and leave one terminal open so
# a viewer can tell at a glance that the stack is up.
xsetroot -solid "#2e3440" 2>/dev/null || true

# Test for a real window, not a live process: an xterm whose window has gone
# lingers as a process and would make a pgrep check report a desktop that is
# actually empty.
if xdotool search --onlyvisible --class xterm >/dev/null 2>&1; then
    echo "terminal    already open"
else
    echo "terminal    starting"
    nohup xterm -geometry 100x28+60+50 -fa Monospace -fs 12 \
        -bg "#1c2028" -fg "#d8dee9" -title "InfantAgent desktop" \
        >"$LOG_DIR/xterm.log" 2>&1 &
    for _ in $(seq 1 20); do
        xdotool search --onlyvisible --class xterm >/dev/null 2>&1 && break
        sleep 0.5
    done
fi

echo
echo "Desktop ready on $DISPLAY_NUM  ->  http://localhost:$NOVNC_PORT/vnc.html"
echo "Logs: $LOG_DIR"
