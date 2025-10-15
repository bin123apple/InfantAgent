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

if ! DISPLAY=:10 xdpyinfo >/dev/null 2>&1; then
  echo "Starting Xvfb :10 ..."
  Xvfb :10 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  sleep 0.7
fi

if DISPLAY=:10 xdpyinfo >/dev/null 2>&1; then
  echo "✅ X OK (:10)"
else
  echo "❗ Xvfb not ready, tail log:"; tail -n 60 /tmp/xvfb.log || true
  exit 1
fi

BIN_DIR="$HOME/.local/bin"; mkdir -p "$BIN_DIR"
WRAP="$BIN_DIR/chrome-fast"

cat > "$WRAP" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:10}"
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