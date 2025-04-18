FROM ubuntu:22.04

# language & timezone
ENV LANG=en_GB.UTF-8
ENV TZ=Europe/London
ENV DEBIAN_FRONTEND=noninteractive

# install gnome desktop and other tools
RUN \
    # Enable partner repository (needed for codecs)
    sed -i 's/# deb http:\/\/archive.canonical.com\/ubuntu bionic partner/deb http:\/\/archive.canonical.com\/ubuntu bionic partner/' /etc/apt/sources.list && \
    # Remove "This system has been minimized" warning.
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
    gdm3 dbus-x11 && \
    # Default libgl1-mesa-dri causes "black window" issues
    # when software rendering. Use ppa to upgrade version.
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
    sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf && \
    rm -f google-chrome-stable_current_amd64.deb

# install 3D accelerated virtual desktops
RUN apt-get update && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
    x11-xserver-utils pkg-config dbus libvdpau1 mesa-vdpau-drivers libegl1-mesa && \
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
    # Install NoMachine Enterprise Desktop
    NOMACHINE_MAJOR_VERSION="8.16-PRODUCTION" && \
    NOMACHINE_VERSION="8.16.1_1" && \
    echo "VERSION: ${NOMACHINE_VERSION}" && \
    echo "MAJOR_VERSION: ${NOMACHINE_MAJOR_VERSION}" && \
    curl -sSL https://download.nomachine.com/packages/${NOMACHINE_MAJOR_VERSION}/Linux/nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb -o nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    dpkg -i nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    rm nomachine-enterprise-desktop_${NOMACHINE_VERSION}_amd64.deb && \
    # Workaround for NoMachine configuring audio for
    # the lightdm user but not for a normal user.
    echo 'mkdir -p ~/.config/pulse\nif [ ! -f ~/.config/pulse/client.conf ]; then\ncp /etc/pulse/client.conf ~/.config/pulse/client.conf\nsed -i "s/; default-server =/default-server = unix:\/tmp\/pulse-socket/g" ~/.config/pulse/client.conf\nfi' > /etc/profile.d/create-pulse-clientconf.sh && \
    echo 'load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse-socket' >> /etc/pulse/default.pa && \
   echo '[GDM]\n# GDM default config, no need to set xserver-command' > /etc/gdm3/custom.conf


# Install dbus-session
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y dbus-user-session
# Nomachine Use EGL capture
RUN sudo /etc/NX/nxserver --eglcapture yes
RUN sudo sed -i '$a WaylandModes "egl,compositor,drm"' /usr/NX/etc/node.cfg
# Turn off Gnome Shell Animations
RUN gsettings set org.gnome.desktop.interface enable-animations false
# Install Vim
RUN sudo apt install -y vim

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

# language and locale settings
RUN apt-get update && \
    apt-get install -y language-pack-zh-hans && \
    sudo sed -i '$a LANG="en_US.UTF-8"\nLANGUAGE="en_US:en:zh_CN:zh"' /etc/environment && \
    touch /var/lib/locales/supported.d/local && \
    sed -i '$a en_US.UTF-8 UTF-8\nzh_CN.UTF-8 UTF-8\nzh_CN.GBK GBK\nzh_CN GB2312' /var/lib/locales/supported.d/local && \
    locale-gen && \
    apt-get install -y fonts-droid-fallback ttf-wqy-zenhei ttf-wqy-microhei fonts-arphic-ukai fonts-arphic-uming fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*
ENV LANGUAGE=en_US:en

# prevent automatic updates and notifications
RUN apt-get remove -y update-notifier update-manager-core update-manager && \
    systemctl disable --now apt-daily-upgrade.timer apt-daily.timer || true && \
    rm -rf /usr/lib/ubuntu-release-upgrader/ && \
    gsettings set org.gnome.software download-updates false && \
    sed -i 's/^Prompt=lts/Prompt=never/' /etc/update-manager/release-upgrades && \
    sed -i 's/^APT::Periodic::Unattended-Upgrade "1";/APT::Periodic::Unattended-Upgrade "0";/' /etc/apt/apt.conf.d/20auto-upgrades && \
    sed -i 's|Exec=/usr/bin/google-chrome-stable %U|Exec=/usr/bin/google-chrome-stable --new-tab chrome://newtab|' /usr/share/applications/google-chrome.desktop

# install xvfb and gnome-session-flashback for headless mode
RUN apt-get update && \
    apt-get install -y xvfb gnome-session-flashback && \
    rm -rf /var/lib/apt/lists/*

# Copy Install Script
COPY GeForce-XorgDisplaySettingAuto.sh /home
COPY Tesla-XorgDisplaySettingAuto.sh /home
COPY vulkan-ubuntu-22.04.sh /home
WORKDIR /home

# RUN chmod +x /home/Tesla-XorgDisplaySettingAuto.sh && \
#     /home/Tesla-XorgDisplaySettingAuto.sh

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
RUN /infant/miniforge3/bin/pip install python-docx PyPDF2 python-pptx pylatexenc openai openpyxl
RUN /infant/miniforge3/bin/pip install python-dotenv toml termcolor pydantic python-docx pyyaml docker pexpect tenacity e2b browsergym minio

# Build
# docker build -t gaia_base_image -f Dockerfile .