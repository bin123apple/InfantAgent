FROM ubuntu:22.04

# language & timezone
ENV LANG=en_GB.UTF-8
ENV TZ=Europe/London
ENV DEBIAN_FRONTEND=noninteractive

# install gnome desktop and otehr tools
RUN \
    # Enable partner repository (needed for codecs)
    sed -i 's/# deb http:\/\/archive.canonical.com\/ubuntu bionic partner/deb http:\/\/archive.canonical.com\/ubuntu bionic partner/' /etc/apt/sources.list && \
    # Remove "This system has been minimized" warning. (which should appear while ssh to the container)
    rm -f /etc/update-motd.d/60-unminimize && \
    rm -f /etc/update-motd.d/98-fsck-at-reboot && \
    # Update base packages.
    apt-get update && DEBIAN_FRONTEND=noninteractive \ 
    apt-get -fy -o Dpkg::Options::="--force-confnew" \
                -o APT::Immediate-Configure=false \
                dist-upgrade && \
    # Base system and tools packages
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y wget gnupg ca-certificates software-properties-common apt-transport-https && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg && \
    install -o root -g root -m 644 packages.microsoft.gpg /usr/share/keyrings/ && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/vscode stable main" > /etc/apt/sources.list.d/vscode.list && \
    rm -f packages.microsoft.gpg && \
    apt-get update && apt-get install -y --no-install-recommends \
    base-files curl ntp add-apt-key aptdaemon \
    apt-transport-https language-pack-en gnome \
    # Ubuntu system packages
    ubuntu-minimal ubuntu-standard ubuntu-desktop \
    gnome-control-center ubuntu-restricted-extras \
    # gnome desktop packages
    gsettings-ubuntu-schemas gnome-system-log \
    gnome-shell-extension-ubuntu-dock \
    gnome-shell-extension-appindicator libpam-kwallet5 \
    gnome-control-center-faces gnome-software-plugin-snap \
    # VSCode
    code \
    # office
    libreoffice libreoffice-l10n-en-gb libreoffice-help-en-gb \
    # email
    thunderbird-locale-en thunderbird-locale-en-us \
    # web browser
    firefox-locale-en \
    fonts-liberation \
    ./google-chrome-stable_current_amd64.deb \
    # File search
    tracker-miner-fs \
    # web tools
    avahi-utils \
    # media tools
    vlc gstreamer1.0-pulseaudio pulseaudio-module-zeroconf \
    pulseaudio-module-bluetooth paprefs pavucontrol libcanberra-pulse \
    # seed client download
    transmission-gtk \
    # printer tools
    cups system-config-printer \
    # system management tools
    synaptic \
    # Figure and design tools
    inkscape gimp \
    # chat and remote access tools
    pidgin remmina \
    remmina-common remmina-plugin-rdp remmina-plugin-vnc \
    # 3D figure tools
    mesa-utils \
    # Install Display Manager and dependencies
    lightdm slick-greeter dbus-x11 && \
    # Default libgl1-mesa-dri causes "black window" issues
    # when software rendering. Use ppa to upgrade version.
    # suitable for intel/AMD and Nvidia GPU.
    add-apt-repository -y ppa:oibaf/graphics-drivers && \
    apt-get update && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y libgl1-mesa-dri && \
    # Stop synaptic package manager being painfully slow
    rm /etc/apt/apt.conf.d/docker-gzip-indexes && \
    rm -rf /var/lib/apt/lists/* && apt-get update && \
    # Generate locales
    echo LANG=$LANG > /etc/default/locale && \
    update-locale LANG=$LANG && \
    # Set up the timezone
    echo $TZ > /etc/timezone && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    DEBIAN_FRONTEND=noninteractive \
    dpkg-reconfigure tzdata && \
    # Configure LightDM Display Manager to use
    # Xephyr instead of X
    # Force to use Xephyr instead of Wayland
    rm /usr/share/lightdm/lightdm.conf.d/50-ubuntu.conf && \
    rm /usr/share/wayland-sessions/*.desktop && \
    rm -f google-chrome-stable_current_amd64.deb && \
    # Reorganise /usr/share/xsessions to set Ubuntu as
    # default session as slick-greeter uses hardcoded names
    # to select the default session.
    rm /usr/share/xsessions/gnome.desktop && \
    mv /usr/share/xsessions/ubuntu.desktop \
       /usr/share/xsessions/ubuntu-xorg.desktop && \
    mv /usr/share/xsessions/gnome-xorg.desktop \
       /usr/share/xsessions/gnome-classic.desktop && \
    echo '#!/bin/bash\nexport XAUTHORITY=/root/.Xauthority.docker\nexport DISPLAY=:0\nexec Xephyr $1 -ac >> /var/log/lightdm/x-1.log' > /usr/bin/Xephyr-lightdm-wrapper && \
    chmod +x /usr/bin/Xephyr-lightdm-wrapper && \
    echo '[LightDM]\nminimum-display-number=1\n[Seat:*]\nuser-session=ubuntu-xorg\nxserver-command=/usr/bin/Xephyr-lightdm-wrapper' > /etc/lightdm/lightdm.conf.d/70-ubuntu.conf && \
    echo '[Greeter]\nbackground=/usr/share/backgrounds/warty-final-ubuntu.png\n' > /etc/lightdm/slick-greeter.conf && \
    # Configure console
    echo "console-setup console-setup/charmap select UTF-8" | debconf-set-selections && \
    # Fix synaptic Empty Dir::Cache::pkgcache setting not
    # handled correctly https://bugs.launchpad.net/ubuntu/+source/synaptic/+bug/1243615
    # which causes synaptic to barf with: E: Could not 
    # open file - open (2: No such file or directory)
    # E: _cache->open() failed, please report.
    sed -i 's/Dir::Cache::pkgcache ""; //' \
        /etc/apt/apt.conf.d/docker-clean && \
    # Disable getty@tty1.service to speed up desktop loading.
    rm -f /etc/systemd/system/getty.target.wants/getty@tty1.service && \
    # Fix issues with slow shutdown
    sed -i 's/#DefaultTimeoutStopSec=90s/DefaultTimeoutStopSec=5s/' /etc/systemd/system.conf && \
    # Fix Polkit issues caused by container login being
    # considered to be an "inactive" session.
    chmod 755 /etc/polkit-1/localauthority && \
    # Date & Time
    echo "[Date & Time]\nIdentity=unix-user:*\nAction=org.gnome.controlcenter.datetime.configure\nResultAny=auth_admin_keep\nResultInactive=auth_admin_keep\nResultActive=auth_admin_keep\n" > /etc/polkit-1/localauthority/50-local.d/10-datetimemechanism.pkla && \
    # User Accounts
    echo "[Manage user accounts]\nIdentity=unix-user:*\nAction=org.gnome.controlcenter.user-accounts.administration\nResultAny=auth_admin_keep\nResultInactive=auth_admin_keep\nResultActive=auth_admin_keep\n" > /etc/polkit-1/localauthority/50-local.d/10-user-accounts.pkla && \
    # Gnome System Log
    echo "[Gnome System Log]\nIdentity=unix-user:*\nAction=org.debian.pkexec.gnome-system-log.run\nResultAny=auth_admin_keep\nResultInactive=auth_admin_keep\nResultActive=auth_admin_keep\n" > /etc/polkit-1/localauthority/50-local.d/10-system-log.pkla && \
    # System Color Manager
    echo "[System Color Manager]\nIdentity=unix-user:*\nAction=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile;org.freedesktop.color-manager.device-inhibit;org.freedesktop.color-manager.sensor-lock\nResultAny=yes\nResultInactive=yes\nResultActive=yes\n" > /etc/polkit-1/localauthority/50-local.d/10-color.pkla && \
    # Shutdown & Restart
    # Note that auth_admin_keep may be better than yes
    # here, but there seems to be an issue with the
    # authentication dialog appearing.
    echo "[Shutdown & Restart]\nIdentity=unix-user:*\nAction=org.freedesktop.login1.power-off;org.freedesktop.login1.power-off-multiple-sessions;org.freedesktop.login1.reboot;org.freedesktop.login1.reboot-multiple-sessions\nResultAny=yes\nResultInactive=yes\nResultActive=yes\n" > /etc/polkit-1/localauthority/50-local.d/10-shutdown.pkla

# install 3D accelerated virtual desktops
RUN apt-get update && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    libvdpau1 mesa-vdpau-drivers libegl1-mesa && \
    VGL_VERSION=$(curl -sSL https://sourceforge.net/projects/virtualgl/files/ | grep "<span class=\"name\">[0-9]" | head -n 1 | cut -d \> -f2 | cut -d \< -f1) && \
    echo "VirtualGL version: ${VGL_VERSION}" && \
    curl -sSL https://altushost-swe.dl.sourceforge.net/project/virtualgl/2.6.95%20%283.0rc1%29/virtualgl_2.6.95_amd64.deb -o virtualgl_2.6.95_amd64.deb && \
    dpkg -i virtualgl_*_amd64.deb && \
    rm virtualgl_*_amd64.deb && \
    echo 'XAUTHORITY=$HOME/.Xauthority.docker' > /etc/profile.d/Xauthority-fix.sh && \
    echo 'export LD_PRELOAD=/usr/lib/libdlfaker.so:/usr/lib/libvglfaker.so:$LD_PRELOAD' > /etc/profile.d/virtualgl.sh && \
    sed -i 's/use-ssh-agent/no-use-ssh-agent/' /etc/X11/Xsession.options

# install nomachine (remote desktop)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    xfonts-base xfonts-75dpi xfonts-100dpi \
    xfonts-scalable net-tools xauth \
    xserver-xorg-video-dummy && \
    # Install NoMachine binary and dependencies.
    # Ensure the nx user ID is not in the normal user range.
    groupadd -r -g 2000 nx && \
    useradd -u 2000 -r -g nx nx && \
    # Try to work out the latest version from the NoMachine
    # Linux download page. If this fails set the following
    # variables manually instead.
    # NOMACHINE_VERSION=$(curl -sSL \
    #   "https://www.nomachine.com/download/download&id=3" |\
    #   grep "Linux/nomachine" |\
    #   cut -d \' -f2 | cut -d \_ -f2-3) && \
    # NOMACHINE_MAJOR_VERSION=$(echo $NOMACHINE_VERSION |\
    #   cut -d \. -f1-2) && \
    # echo "VERSION: ${NOMACHINE_VERSION}" && \
    # echo "MAJOR_VERSION: ${NOMACHINE_MAJOR_VERSION}" && \
    # curl -sSL https://download.nomachine.com/download/${NOMACHINE_MAJOR_VERSION}/Linux/nomachine_${NOMACHINE_VERSION}_amd64.deb -o nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    # dpkg -i nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    # rm nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    # NOMACHINE_MAJOR_VERSION="8.14-PRODUCTION" && \
    # NOMACHINE_VERSION="8.14.2_1" && \
    NOMACHINE_MAJOR_VERSION="8.16-PRODUCTION" && \
    NOMACHINE_VERSION="8.16.1_1" && \
    echo "VERSION: ${NOMACHINE_VERSION}" && \
    echo "MAJOR_VERSION: ${NOMACHINE_MAJOR_VERSION}" && \
    # curl -sSL https://download.nomachine.com/download/${NOMACHINE_MAJOR_VERSION}/Linux/nomachine_${NOMACHINE_VERSION}_amd64.deb -o nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    # dpkg -i nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    # rm nomachine_${NOMACHINE_VERSION}_amd64.deb && \
    curl -sSL https://download.nomachine.com/packages/${NOMACHINE_MAJOR_VERSION}/Linux/nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb -o nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    dpkg -i nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    rm nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    # Workaround for NoMachine configuring audio for
    # the lightdm user but not for a normal user.
    echo 'mkdir -p ~/.config/pulse\nif [ ! -f ~/.config/pulse/client.conf ]; then\ncp /etc/pulse/client.conf ~/.config/pulse/client.conf\nsed -i "s/; default-server =/default-server = unix:\/tmp\/pulse-socket/g" ~/.config/pulse/client.conf\nfi' > /etc/profile.d/create-pulse-clientconf.sh && \
    echo 'load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse-socket' >> /etc/pulse/default.pa && \
   echo '[LightDM]\nminimum-display-number=1\n[Seat:*]\nuser-session=ubuntu-xorg\nxserver-command=Xorg -ac' > /etc/lightdm/lightdm.conf.d/70-ubuntu.conf

COPY xorg.conf /etc/X11/xorg.conf

# Debug for VirtualDesktop
# Display Number -> :0
RUN sudo sed -i 's/minimum-display-number=1/minimum-display-number=0/g' /etc/lightdm/lightdm.conf.d/70-ubuntu.conf
# Comment Optional pam_keallt*
RUN sudo sed -i 's/auth    optional        pam_kwallet.so/#auth    optional        pam_kwallet.so/g' /etc/pam.d/lightdm
RUN sudo sed -i 's/auth    optional        pam_kwallet5.so/#auth    optional        pam_kwallet5.so/g' /etc/pam.d/lightdm
# Install dbus-session
RUN sudo apt install -y dbus-user-session
# Nomachine Use EGL capture
RUN sudo /etc/NX/nxserver --eglcapture yes
RUN sudo sed -i '$a WaylandModes "egl,compositor,drm"' /usr/NX/etc/node.cfg
# Turn off Gnome Shell Animations
RUN gsettings set org.gnome.desktop.interface enable-animations false
# Install Vim
RUN sudo apt install -y vim
# Copy Install Script
COPY GeForce-XorgDisplaySettingAuto.sh /home
COPY Tesla-XorgDisplaySettingAuto.sh /home
# RUN chmod +x /home/Tesla-XorgDisplaySettingAuto.sh && \
#     /home/Tesla-XorgDisplaySettingAuto.sh
# COPY vulkan-ubuntu-18.04.sh /home
COPY vulkan-ubuntu-22.04.sh /home
WORKDIR /home

# install basic packages
RUN apt-get update && apt-get install -y \
    xdotool \
    curl \
    wget \
    git \
    vim \
    nano \
    unzip \
    zip \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    openssh-server \
    sudo \
    gcc \
    jq \
    g++ \
    make \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p -m0755 /var/run/sshd

# symlink python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

# ==== infant Runtime Client ====
RUN mkdir -p /infant && mkdir -p /infant/logs && chmod 777 /infant/logs
RUN wget --progress=bar:force -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
RUN bash Miniforge3.sh -b -p /infant/miniforge3
RUN chmod -R g+w /infant/miniforge3
RUN bash -c ". /infant/miniforge3/etc/profile.d/conda.sh && conda config --set changeps1 False && conda config --append channels conda-forge"
RUN echo "" > /infant/bash.bashrc
RUN rm -f Miniforge3.sh

# - agentskills dependencies
RUN /infant/miniforge3/bin/pip install --upgrade pip
RUN /infant/miniforge3/bin/pip install jupyterlab notebook jupyter_kernel_gateway flake8 Pillow
RUN /infant/miniforge3/bin/pip install python-docx PyPDF2 python-pptx pylatexenc openai
RUN /infant/miniforge3/bin/pip install python-dotenv toml termcolor pydantic python-docx pyyaml docker pexpect tenacity e2b browsergym minio

# No password login


# Build
# docker build -t ubuntu-gnome-nomachine:22.04 -f Dockerfile .