#!/bin/bash
# set up user
echo "127.0.0.1    infant-computer" | sudo tee -a /etc/hosts
# echo "Please set $CreateUserAccount password:"
sudo adduser $CreateUserAccount
# Add user to nopasswdlogin
sudo usermod -aG nopasswdlogin $CreateUserAccount
echo "Install NVIDIA Driver"
sudo /etc/init.d/lightdm stop
# Install NVIDIA drivers, including X graphic drivers by omitting --x-{prefix,module-path,library-path,sysconfig-path}
if ! command -v nvidia-xconfig &> /dev/null; then
  export DRIVER_VERSION=$(head -n1 </proc/driver/nvidia/version | awk '{print $10}')
  BASE_URL=https://cn.download.nvidia.com/tesla
  cd /tmp
  sudo curl -fsSL -O $BASE_URL/$DRIVER_VERSION/NVIDIA-Linux-x86_64-$DRIVER_VERSION.run
  sudo sh NVIDIA-Linux-x86_64-$DRIVER_VERSION.run -x
  cd NVIDIA-Linux-x86_64-$DRIVER_VERSION
  sudo ./nvidia-installer --silent \
                    --no-kernel-module \
                    --install-compat32-libs \
                    --no-nouveau-check 
  sudo rm -rf /tmp/NVIDIA*
  cd ~
fi

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

# Put the following in Dock 
new_apps="['google-chrome.desktop', 'code.desktop', 'thunderbird.desktop', 'libreoffice-writer.desktop', 'libreoffice-calc.desktop', 'libreoffice-impress.desktop']"
gsettings set org.gnome.shell favorite-apps "$new_apps"

# Fix Nomachine lag issue
echo 'setting up xvfb'
sudo systemctl stop gdm3
Xvfb :0 -screen 0 1920x1080x24 &
export DISPLAY=:0
unset LD_PRELOAD
gnome-session &

sleep 5
sudo /etc/NX/nxserver --restart
sudo tail -n 100 /usr/NX/var/log/nxserver.log > /tmp/nxserver_restart.log