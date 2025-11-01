PYTHON_SETUP_CODE = """import subprocess, textwrap

CHROME_FAST_CODE = textwrap.dedent(r\"\"\"\
cat > ~/setup_chrome_fast_user.sh <<'__SH__'
#!/usr/bin/env bash
set -euo pipefail

if command -v google-chrome-stable >/dev/null 2>&1; then
  CHROME_BIN="$(command -v google-chrome-stable)"
elif [ -x /opt/google/chrome/chrome ]; then
  CHROME_BIN="/opt/google/chrome/chrome"
else
  echo "❌ Did not find google-chrome-stable 或 /opt/google/chrome/chrome"
  exit 1
fi
echo "✅ Chrome: $CHROME_BIN"

XAUTH="$HOME/.Xauthority"
touch "$XAUTH"; chmod 600 "$XAUTH"
rm -f "$XAUTH"-c "$XAUTH"-l "$XAUTH".lock 2>/dev/null || true

COOKIE="$(XAUTHORITY="$XAUTH" xauth list 2>/dev/null | awk '/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}')"
[ -n "$COOKIE" ] || COOKIE="$(mcookie)"
HOST="$(hostname)"

for name in ":10" "$HOST/unix:10" "localhost/unix:10"; do
  XAUTHORITY="$XAUTH" xauth add "$name" . "$COOKIE" 2>/dev/null || true
done

C2="$(xauth -f "$XAUTH" list | awk '$1 ~ /(^|\\/ )unix:10$/ && $3=="MIT-MAGIC-COOKIE-1" {print $NF; exit}')"
[ -n "$C2" ] || C2="$(xauth -f "$XAUTH" list | awk '/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}')"
for name in ":10" "$HOST/unix:10" "localhost/unix:10"; do
  xauth -f "$XAUTH" add "$name" . "$C2" 2>/dev/null || true
done

rm -f /tmp/.X10-lock 2>/dev/null || true
mkdir -p /tmp/.X11-unix 2>/dev/null || true

if ! DISPLAY=:99 xdpyinfo >/dev/null 2>&1; then
  echo "Starting Xvfb :99 ..."
  Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  sleep 0.7
fi

if DISPLAY=:99 xdpyinfo >/dev/null 2>&1; then
  echo "✅ X OK (:99)"
else
  echo "❗ Xvfb not ready, tail log:"; tail -n 60 /tmp/xvfb.log || true
  exit 1
fi

BIN_DIR="$HOME/.local/bin"; mkdir -p "$BIN_DIR"
WRAP="$BIN_DIR/chrome-fast"

cat > "$WRAP" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-$USER}"
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true

rm -f /tmp/.X10-lock 2>/dev/null || true
if ! xdpyinfo >/dev/null 2>&1; then
  pgrep -x Xvfb >/dev/null 2>&1 || Xvfb :10 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  sleep 0.7
fi

USER_DATA_DIR="${USER_DATA_DIR:-$HOME/chrome-profile}"
mkdir -p "$USER_DATA_DIR"
rm -f "$HOME/.config/google-chrome/Singleton"* /tmp/.com.google.Chrome*/SingletonSocket 2>/dev/null || true

LOG_FLAGS=()
[ "${CHROME_LOG:-0}" = "1" ] && { export CHROME_LOG_FILE="/tmp/chrome_debug.log"; LOG_FLAGS+=(--enable-logging --v=1 --log-file="$CHROME_LOG_FILE"); }
CDP_FLAGS=()
[ "${DEBUG_CDP:-0}" = "1" ] && CDP_FLAGS+=(--remote-debugging-port=9222 --remote-debugging-address=127.0.0.1)

EXTRA_FLAGS=(
  --password-store=basic
  --use-mock-keychain
  --use-gl=angle
  --use-angle=swiftshader
  --no-first-run
  --user-data-dir="$USER_DATA_DIR"
  --profile-directory=Default
  --start-maximized
)

exec __CHROME_BIN__ \\
  "${LOG_FLAGS[@]}" \\
  "${CDP_FLAGS[@]}" \\
  "${EXTRA_FLAGS[@]}" \\
  "$@"
SH

sed -i "s|__CHROME_BIN__|${CHROME_BIN}|g" "$WRAP"
chmod +x "$WRAP"

APPS_USER="$HOME/.local/share/applications"; mkdir -p "$APPS_USER"
for F in /usr/share/applications/google-chrome.desktop /usr/share/applications/com.google.Chrome.desktop; do
  [ -f "$F" ] || continue
  cp "$F" "$APPS_USER/$(basename "$F")"
  sed -i "s|^Exec=.*|Exec=${WRAP} %U|" "$APPS_USER/$(basename "$F")"
done
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_USER" >/dev/null 2>&1 || true

echo "CHROME_LOG=1 DEBUG_CDP=0 $WRAP about:blank &"
__SH__
chmod +x ~/setup_chrome_fast_user.sh
~/setup_chrome_fast_user.sh
\"\"\")

try:
    result = subprocess.run(
        ["bash", "-lc", CHROME_FAST_CODE],
        check=True,
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
except subprocess.CalledProcessError as e:
    print("Script failed with return code:", e.returncode)
    print("--- STDOUT ---", e.stdout)
    print("--- STDERR ---", e.stderr)
    raise

"""

PYTHON_SETUP_CODE_VIRTUAL_CONNECTION = """import subprocess, textwrap

CHROME_FAST_CODE = textwrap.dedent(r\"\"\"\
cat > ~/setup_virtual_connection.sh <<'__SH__'
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y freerdp2-x11

RDP_USER="${RDP_USER:-infant}"
RDP_PASS="${RDP_PASS:-123}"
RDP_HOST="${RDP_HOST:-127.0.0.1}"
RDP_PORT="${RDP_PORT:-3389}"

HN="$(cat /etc/hostname 2>/dev/null || echo "")"
if [ -n "$HN" ] && ! grep -qE "^[[:space:]]*127\.0\.1\.1[[:space:]]+$HN( |\$)" /etc/hosts 2>/dev/null; then
  echo "-> add 127.0.1.1 $HN to /etc/hosts"
  echo "127.0.1.1 $HN" | sudo tee -a /etc/hosts >/dev/null
fi

echo "== stop xrdp/xrdp-sesman/guacd & free :10 =="
if [ "${DISPLAY:-}" = ":10" ]; then
  echo "⚠️ Current DISPLAY is :10, skipping killing Xorg/Xvfb :10 to avoid self-termination"
else
  sudo pkill -9 -f 'Xorg .*:10'  2>/dev/null || true
  sudo pkill -9 -f 'Xvfb .*:10'  2>/dev/null || true
fi
sudo pkill -9 -x xrdp-sesman 2>/dev/null || true
sudo pkill -9 -x xrdp        2>/dev/null || true
sudo pkill -9 -x guacd       2>/dev/null || true

sudo mkdir -p /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix 2>/dev/null || true
sudo rm -f /tmp/.X11-unix/X10 /tmp/.X10-lock

SESINI="/etc/xrdp/sesman.ini"
sudo cp -a "$SESINI" "${SESINI}.bak.$(date +%s)" || true
if sudo grep -q "^X11DisplayOffset" "$SESINI"; then
  sudo sed -i 's/^X11DisplayOffset=.*/X11DisplayOffset=10/' "$SESINI"
else
  if sudo grep -q "^\[Xorg\]" "$SESINI"; then
    sudo awk '1; /^\[Xorg\]$/ {print "X11DisplayOffset=10"}' "$SESINI" | sudo tee "$SESINI" >/dev/null
  else
    echo -e "\n[Xorg]\nX11DisplayOffset=10" | sudo tee -a "$SESINI" >/dev/null
  fi
fi
if sudo grep -q "^MaxSessions" "$SESINI"; then
  sudo sed -i 's/^MaxSessions=.*/MaxSessions=1/' "$SESINI"
else
  echo "MaxSessions=1" | sudo tee -a "$SESINI" >/dev/null
fi

if ! grep -q "^\[Xorg\]" /etc/xrdp/xrdp.ini; then
  echo "⚠️ /etc/xrdp/xrdp.ini does not have [Xorg] section"
fi

if [ -f /etc/X11/Xwrapper.config ]; then
  sudo sed -i 's/^allowed_users=.*/allowed_users=anybody/' /etc/X11/Xwrapper.config
fi

echo "== start xrdp services =="
sudo sh -c '/usr/sbin/xrdp-sesman -n >>/tmp/xrdp-sesman.fg.log 2>&1 &' 
sleep 0.2
sudo sh -c '/usr/sbin/xrdp        -n >>/tmp/xrdp.fg.log        2>&1 &'
sleep 0.2
sudo sh -c '/usr/sbin/guacd       -f >>/tmp/guacd.fg.log       2>&1 &' || true
sleep 0.5

echo "-> listen ports:"
ss -lntp | egrep '(:3389|:4822)' || { echo "❌ xrdp services not running"; exit 1; }

pick_free_x() { for d in 90 91 92 93 94 95 96 97 98 99 100; do
  [ ! -S "/tmp/.X11-unix/X$d" ] && [ ! -f "/tmp/.X$d-lock" ] && { echo ":$d"; return 0; }
done; return 1; }
FAKE_DISPLAY="$(pick_free_x)" || { echo "❌ cannot find free X display for temporary Xvfb"; exit 1; }

XAUTH="$HOME/.Xauthority"; touch "$XAUTH"; chmod 600 "$XAUTH"
COOKIE="$(mcookie)"
xauth -f "$XAUTH" remove "$FAKE_DISPLAY" 2>/dev/null || true
xauth -f "$XAUTH" add "$FAKE_DISPLAY" . "$COOKIE"

nohup Xvfb "$FAKE_DISPLAY" -screen 0 1280x800x24 -auth "$XAUTH" -nolisten tcp > /tmp/xvfb_rdp.log 2>&1 &
for i in {1..40}; do DISPLAY="$FAKE_DISPLAY" XAUTHORITY="$XAUTH" xdpyinfo >/dev/null 2>&1 && break; sleep 0.2; done
DISPLAY="$FAKE_DISPLAY" XAUTHORITY="$XAUTH" xdpyinfo >/dev/null || { echo "❌ temp Xvfb is not ready"; sed -n '1,120p' /tmp/xvfb_rdp.log; exit 1; }

echo "-- test login to trigger sesman ---"
DISPLAY="$FAKE_DISPLAY" timeout 8s xfreerdp \
  /v:"$RDP_HOST:$RDP_PORT" /u:"$RDP_USER" /p:"$RDP_PASS" /cert:ignore \
  /size:1280x800 /rfx /log-level:WARN || true

DISP="$(
  sudo -n tac /var/log/xrdp-sesman.log 2>/dev/null \
  | grep -oE 'display :[0-9]+(\.0)?' \
  | head -n1 \
  | grep -oE ':[0-9]+'
)"
echo "-> sesman display: ${DISP:-<none>}"

if [ "$DISP" != ":10" ]; then
  echo "❌ expected display :10 but got '${DISP:-<none>}'"
  SESPID="$(pgrep -x xrdp-sesman | head -n1)"
  if [ -n "$SESPID" ] && command -v nsenter >/dev/null 2>&1; then
    sudo nsenter -t "$SESPID" -a bash -lc 'fuser -v /tmp/.X11-unix/X10 2>/dev/null || echo "(ns no body is using)"; ps -ef | egrep -i "X(org|vfb) :10" | grep -v grep || true'
  else
    fuser -v /tmp/.X11-unix/X10 2>/dev/null || echo "No body is using (no nsenter)"
    ps -ef | egrep -i 'X(org|vfb) :10' | grep -v grep || true
  fi
  sudo tail -n 120 /var/log/xrdp.log || true
  sudo tail -n 120 /var/log/xrdp-sesman.log || true
  exit 1
fi

AUTH="$(ps -eo pid,args | awk -v d=":10" '$0 ~ "Xorg " d {for(i=1;i<=NF;i++) if ($i=="-auth"){print $(i+1); exit}}')"
[ -z "$AUTH" ] && AUTH="$HOME/.Xauthority"
export DISPLAY=":10"
export XAUTHORITY="$AUTH"
unset LD_PRELOAD VGL_DISPLAY VGL_CLIENT VGL_READBACK || true

pkill -9 -f "Xvfb $FAKE_DISPLAY" 2>/dev/null || true
rm -f "/tmp/.X11-unix/X${FAKE_DISPLAY#:}" "/tmp/.X${FAKE_DISPLAY#:}-lock" 2>/dev/null || true

echo "✅ Fix DISPLAY=:10, XAUTHORITY=$XAUTHORITY"
__SH__
chmod +x ~/setup_virtual_connection.sh
~/setup_virtual_connection.sh
\"\"\")

try:
    result = subprocess.run(
        ["bash", "-lc", CHROME_FAST_CODE],
        check=True,
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
except subprocess.CalledProcessError as e:
    print("Script failed with return code:", e.returncode)
    print("--- STDOUT ---", e.stdout)
    print("--- STDERR ---", e.stderr)
    raise

"""