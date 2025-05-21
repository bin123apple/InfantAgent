#!/bin/bash
# set up user
echo "127.0.0.1    infant-computer" | sudo tee -a /etc/hosts
echo "Please set $CreateUserAccount password:"
sudo adduser $CreateUserAccount
# Add user to nopasswdlogin
sudo usermod -aG nopasswdlogin $CreateUserAccount
sudo /etc/init.d/lightdm stop

echo "Installing NVIDIA Driver"
export DRIVER_VERSION=$(
  { grep -oE '[0-9]+\.[0-9]+\.[0-9]+' /proc/driver/nvidia/version 2>/dev/null \
    || nvidia-smi --query-gpu=driver_version --format=csv,noheader; } | head -n1)

candidates=(
  "12.9.0"
  "12.8.1"
  "12.8.0"
  "12.7.1"
  "12.7.0"
  "12.6.0"
  "12.5.2"
  "12.5.0"
  "12.4.1"
  "12.4.0"
  "12.3.1"
  "12.3.0"
  "12.2.2"
  "12.2.0"
)

gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "")
if echo "$gpu_name" | grep -Eiq 'GeForce|RTX|Quadro'; then
  BASE_URL="https://developer.download.nvidia.com/compute/cuda"
else
  BASE_URL="https://developer.download.nvidia.com/compute/cuda"
fi

FOUND=""
for cuda in "${candidates[@]}"; do
  URL="${BASE_URL}/${cuda}/local_installers/cuda_${cuda}_${DRIVER_VERSION}_linux.run"
  if curl -sfI "$URL" &>/dev/null; then
    FOUND="$cuda"
    echo "Found matching CUDA bundle: $cuda"
    break
  fi
done

if [[ -z "$FOUND" ]]; then
  echo "Error: no CUDA installer found for driver ${DRIVER_VERSION}" >&2
  exit 1
fi

curl -fSL -o cuda_${FOUND}_${DRIVER_VERSION}.run \
     "${BASE_URL}/${FOUND}/local_installers/cuda_${FOUND}_${DRIVER_VERSION}_linux.run"

sh cuda_${FOUND}_${DRIVER_VERSION}.run --silent --extract=/tmp/cuda_pkg
sudo sh /tmp/cuda_pkg/NVIDIA-Linux-x86_64-${DRIVER_VERSION}.run \
     --silent --no-kernel-modules --install-compat32-libs --no-nouveau-check
rm cuda_${FOUND}_${DRIVER_VERSION}.run
rm -rf /tmp/cuda_pkg

# Check if GPU rendering is set
if [ "$RenderType" == "Gpu" ]; then
  echo "Using GPU rendering, starting virtual display configuration"
  # GPU rendering: configure virtual display
  echo "X11 set"

  if [ -f "/etc/X11/xorg.conf" ]; then
    sudo rm /etc/X11/xorg.conf
  fi

  echo "UUID"
  if [ "$NVIDIA_VISIBLE_DEVICES" == "all" ]; then
    export GPU_SELECT=$(sudo nvidia-smi --query-gpu=uuid --format=csv | sed -n 2p)
  elif [ -z "$NVIDIA_VISIBLE_DEVICES" ]; then
    export GPU_SELECT=$(sudo nvidia-smi --query-gpu=uuid --format=csv | sed -n 2p)
  else
    export GPU_SELECT=$(sudo nvidia-smi --id=$(echo "$NVIDIA_VISIBLE_DEVICES" | cut -d ',' -f1) --query-gpu=uuid --format=csv | sed -n 2p)
    if [ -z "$GPU_SELECT" ]; then
      export GPU_SELECT=$(sudo nvidia-smi --query-gpu=uuid --format=csv | sed -n 2p)
    fi
  fi

  if [ -z "$GPU_SELECT" ]; then
    echo "No NVIDIA GPUs detected. Exiting."
    exit 1
  fi

  echo "Allow Empty"
  export SIZEW=1920
  export SIZEH=1200
  export CDEPTH=24
  HEX_ID=$(sudo nvidia-smi --query-gpu=pci.bus_id --id="$GPU_SELECT" --format=csv | sed -n 2p)
  IFS=":." ARR_ID=($HEX_ID)
  BUS_ID=PCI:$((16#${ARR_ID[1]})):$((16#${ARR_ID[2]})):$((16#${ARR_ID[3]}))
  export MODELINE=$(cvt -r ${SIZEW} ${SIZEH} | sed -n 2p)
  sudo nvidia-xconfig --virtual="${SIZEW}x${SIZEH}" --depth="$CDEPTH" --allow-empty-initial-configuration --busid="$BUS_ID" 
  sudo sed -i '/Driver\s\+"nvidia"/a\    Option       "HardDPMS" "false"' /etc/X11/xorg.conf
  sudo sed -i '/Section\s\+"Monitor"/a\    '"$MODELINE" /etc/X11/xorg.conf
  sudo sed -i '/SubSection\s\+"Display"/a\        Viewport 0 0' /etc/X11/xorg.conf
  sudo sed -i '/Section\s\+"ServerLayout"/a\    Option "AllowNVIDIAGPUScreens"' /etc/X11/xorg.conf
else
  echo "Using default CPU rendering mode"
fi

# Disable GNOME animations (optional, for performance)
sudo gsettings set org.gnome.desktop.interface enable-animations false

# Configure GDM3 for automatic login
if [ -f /etc/gdm3/custom.conf ]; then
    sudo sed -i "/^#  AutomaticLoginEnable = true/ s/^# //" /etc/gdm3/custom.conf
    sudo sed -i "/^#  AutomaticLogin =/ s/^# //" /etc/gdm3/custom.conf
    sudo sed -i "/^AutomaticLogin =/c\AutomaticLogin = infant" /etc/gdm3/custom.conf
else
    echo -e "[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=infant" | sudo tee /etc/gdm3/custom.conf > /dev/null
fi

# Restart GDM3 to apply changes
sudo systemctl restart gdm3

# Print completion message
echo "xdotool installed and automatic login configured."

# Remove update notifier
sudo apt remove update-notifier update-manager-core update-manager
sudo systemctl disable --now apt-daily-upgrade.timer apt-daily.timer
sudo rm -rf /usr/lib/ubuntu-release-upgrader/
# sudo systemctl status unattended-upgrades
gsettings set org.gnome.software download-updates false
sed -i 's/^Prompt=lts/Prompt=never/' /etc/update-manager/release-upgrades
sed -i 's/^APT::Periodic::Unattended-Upgrade "1";/APT::Periodic::Unattended-Upgrade "0";/' /etc/apt/apt.conf.d/20auto-upgrades

# Edit Chrome desktop file to open new tab on startup
sudo sed -i 's|Exec=/usr/bin/google-chrome-stable %U|Exec=/usr/bin/google-chrome-stable --new-tab chrome://newtab|' /usr/share/applications/google-chrome.desktop

# Put the following in Dock 
new_apps="['google-chrome.desktop', 'code.desktop', 'thunderbird.desktop', 'libreoffice-writer.desktop', 'libreoffice-calc.desktop', 'libreoffice-impress.desktop']"
gsettings set org.gnome.shell favorite-apps "$new_apps"

# Install Chinese language support
sudo apt-get update
sudo apt-get install -y language-pack-zh-hans
sudo sed -i '$a LANG="zh_CN.UTF-8"\nLANGUAGE="zh_CN:zh:en_US:en"' /etc/environment
sudo touch /var/lib/locales/supported.d/local
sudo sed -i '$a en_US.UTF-8 UTF-8\nzh_CN.UTF-8 UTF-8\nzh_CN.GBK GBK\nzh_CN GB2312' /var/lib/locales/supported.d/local
sudo locale-gen
sudo apt-get install -y fonts-droid-fallback ttf-wqy-zenhei ttf-wqy-microhei fonts-arphic-ukai fonts-arphic-uming

# Fix Nomachine lag issue
echo 'setting up xvfb'
sudo systemctl stop gdm3
sudo apt-get install -y xvfb
Xvfb :0 -screen 0 1920x1080x24 &
export DISPLAY=:0
unset LD_PRELOAD
sudo apt-get install -y gnome-session-flashback
gnome-session &

sleep 5
sudo /etc/NX/nxserver --restart
sudo tail -n 100 /usr/NX/var/log/nxserver.log > /tmp/nxserver_restart.log
