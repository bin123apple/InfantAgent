FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV TZ=America/New_York

# ---- Base OS, GNOME desktop, tools ----
RUN rm -f /etc/update-motd.d/60-unminimize /etc/update-motd.d/98-fsck-at-reboot && \
    apt-get update && \
    apt-get -y -o Dpkg::Options::="--force-confnew" -o APT::Immediate-Configure=false dist-upgrade && \
    apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg software-properties-common apt-transport-https locales \
      gnome ubuntu-desktop gdm3 dbus-x11 \
      mesa-utils libegl1-mesa libvdpau1 && \
    sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf && \
    echo "$TZ" > /etc/timezone && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    apt-get install -y tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ---- XRDP (RDP server for the desktop) ----
RUN apt-get update && apt-get install -y --no-install-recommends xrdp && \
    adduser xrdp ssl-cert || true && \
    printf "export DESKTOP_SESSION=gnome\nexec gnome-session\n" > /etc/xrdp/startwm.sh && \
    chmod +x /etc/xrdp/startwm.sh && \
    rm -rf /var/lib/apt/lists/*

# # ---- Create a login user (change as needed) ----
# ARG DESKTOP_USER=infant
# ARG DESKTOP_PASS=123
# RUN if ! id -u "${DESKTOP_USER}" >/dev/null 2>&1; then useradd -m -s /bin/bash "${DESKTOP_USER}"; fi && \
#     echo "${DESKTOP_USER}:${DESKTOP_PASS}" | chpasswd && \
#     usermod -aG sudo "${DESKTOP_USER}"

# ---- Tomcat + Guacamole WebApp + guacd (all-in-one) ----
ENV GUAC_VERSION=1.5.5
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tomcat9 tomcat9-admin tomcat9-common \
        guacd libguac-client-rdp0 libguac-client-vnc0 libguac-client-ssh0 && \
    rm -rf /var/lib/apt/lists/*

    RUN mkdir -p /var/lib/tomcat9/webapps /etc/guacamole && \
    wget -q https://downloads.apache.org/guacamole/${GUAC_VERSION}/binary/guacamole-${GUAC_VERSION}.war \
      -O /var/lib/tomcat9/webapps/guacamole.war || \
    wget -q https://archive.apache.org/dist/guacamole/${GUAC_VERSION}/binary/guacamole-${GUAC_VERSION}.war \
      -O /var/lib/tomcat9/webapps/guacamole.war && \
    ln -sf /etc/guacamole /usr/share/tomcat9/.guacamole

# guacd.conf
RUN mkdir -p /etc/guacamole && \
    cat >/etc/guacamole/guacd.conf <<EOF
[daemon]
log_level = info

[server]
bind_host = 0.0.0.0
bind_port = 4822
EOF

# guacamole.properties pointing to local guacd
RUN cat >/etc/guacamole/guacamole.properties <<EOF
guacd-hostname: localhost
guacd-port: 4822
EOF

# ---------- Tools & i18n (optional) ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
      vim nano git unzip zip openssh-server python3 python3-pip \
      fonts-noto-color-emoji language-pack-zh-hans && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    locale-gen en_US.UTF-8 zh_CN.UTF-8
ENV LANGUAGE=en_US:en

# ---------- Startup ----------
RUN cat >/usr/local/bin/start-all.sh <<'EOF'
#!/usr/bin/env bash
set -e
# DBus (GNOME expects it)
if command -v service >/dev/null 2>&1; then service dbus start || true; else dbus-daemon --system --fork || true; fi
# XRDP
mkdir -p /var/run/xrdp; chown xrdp:xrdp /var/run/xrdp || true
/usr/sbin/xrdp-sesman -n &
/usr/sbin/xrdp -n &
# guacd
/usr/sbin/guacd -f &
# Tomcat (serves /guacamole on :8080)
exec catalina.sh run
EOF
RUN chmod +x /usr/local/bin/start-all.sh


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

# Install dbus-session
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y dbus-user-session

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
RUN [ -e /usr/bin/python ] || ln -s /usr/bin/python3 /usr/bin/python

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
# Disable APT periodic & unattended upgrades in containers (no systemctl, no gsettings)
RUN set -eux; \
    apt-get update; \
    apt-get -y remove unattended-upgrades || true; \
    printf 'APT::Periodic::Enable "0";\nAPT::Periodic::Update-Package-Lists "0";\nAPT::Periodic::Download-Upgradeable-Packages "0";\nAPT::Periodic::AutocleanInterval "0";\n' \
      > /etc/apt/apt.conf.d/10periodic; \
    printf 'APT::Periodic::Unattended-Upgrade "0";\n' \
      > /etc/apt/apt.conf.d/20auto-upgrades; \
    if [ -f /etc/update-manager/release-upgrades ]; then \
      sed -i 's/^Prompt=.*/Prompt=never/' /etc/update-manager/release-upgrades; \
    fi; \
    if [ -f /usr/share/applications/google-chrome.desktop ]; then \
      sed -i 's|Exec=/usr/bin/google-chrome-stable %U|Exec=/usr/bin/google-chrome-stable --new-tab chrome://newtab|' /usr/share/applications/google-chrome.desktop; \
    fi

# install xvfb and gnome-session-flashback for headless mode
RUN apt-get update && \
    apt-get install -y xvfb gnome-session-flashback && \
    rm -rf /var/lib/apt/lists/*

# Copy Install Script
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
RUN apt-get autoclean
RUN /infant/miniforge3/bin/pip install --upgrade pip
RUN /infant/miniforge3/bin/pip install --no-cache-dir jupyterlab notebook jupyter_kernel_gateway flake8 Pillow python-docx PyPDF2 python-pptx pylatexenc openai openpyxl python-dotenv toml termcolor pydantic python-docx pyyaml docker pexpect tenacity e2b browsergym minio


EXPOSE 3389 8080
CMD ["/usr/local/bin/start-all.sh"]

# Build
# docker build -t ubuntu-gnome-nomachine:latest -f Dockerfile .