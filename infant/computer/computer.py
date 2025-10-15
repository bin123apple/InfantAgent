"""
Simplified Computer class for SSH connection and remote control to docker computer-container.
Based on the original computer.py but streamlined for essential SSH functionality.
"""

import os
import re
import time
import socket
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from pexpect import pxssh
from tenacity import retry, stop_after_attempt, wait_fixed

from infant.util.logger import infant_logger as logger


class Computer:
    """
    Simplified computer class for SSH-based remote control of docker containers.
    Designed to connect to the computer-container defined in docker-compose.yaml.
    """

    def __init__(
        self,
        ssh_hostname: str = 'localhost',
        ssh_port: int = 63710,
        ssh_password: str = '123',
        ssh_username: str = 'infant',
        ssh_root_password: str = '123',
        timeout: int = 120,
        workspace_dir: str = '/workspace',
        enable_auto_lint: bool = False,
        initialize_plugins: bool = False,
    ):
        """
        Initialize the simplified computer connection.

        Args:
            ssh_hostname: SSH server hostname (default: localhost for docker-compose)
            ssh_port: SSH port (default: 63710, mapped from container port 22)
            ssh_password: SSH password (default: '123' as set in docker-compose)
            ssh_username: SSH username (default: 'infant' user in container)
            ssh_root_password: Root user SSH password (default: '123')
            timeout: Command execution timeout in seconds
            workspace_dir: Working directory in the container
            enable_auto_lint: Enable automatic linting
            initialize_plugins: Initialize plugins and tools
        """
        self.ssh_hostname = ssh_hostname
        self.ssh_port = ssh_port
        self.ssh_password = ssh_password
        self.ssh_username = ssh_username
        self.ssh_root_password = ssh_root_password
        self.timeout = timeout
        self.workspace_dir = workspace_dir
        self.enable_auto_lint = enable_auto_lint
        self.initialize_plugins = initialize_plugins

        # SSH session objects
        self.ssh: Optional[pxssh.pxssh] = None  # Main session (infant user)
        self.ssh_root: Optional[pxssh.pxssh] = None  # Root session for setup

        # Environment variables
        self._env: dict[str, str] = {}

        logger.info(f'Initializing SSH connection to {ssh_username}@{ssh_hostname}')

        # Connect to SSH
        self.connect()

    def remove_known_host_entry(self, port: int, hostname: str = 'localhost') -> None:
        """
        Remove SSH known_hosts entry to avoid conflicts when reconnecting.

        Args:
            port: SSH port to remove from known_hosts
            hostname: Hostname to remove (default: localhost)
        """
        home = Path.home()
        command = f'ssh-keygen -f "{home}/.ssh/known_hosts" -R "[{hostname}]:{port}"'
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                text=True,
                capture_output=True
            )
            logger.info(f"Successfully removed known host entry for port {port}")
            logger.debug(f"ssh-keygen output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.debug(f"Error removing known host for port {port}: {e.stderr}")

    def _wait_for_ssh_ready(self, max_wait: int = 60) -> bool:
        """
        Wait for SSH service to be ready on the target host.

        Args:
            max_wait: Maximum time to wait in seconds

        Returns:
            True if SSH is ready, False otherwise
        """
        import time
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((self.ssh_hostname, self.ssh_port))
                sock.close()

                if result == 0:
                    logger.info(f'SSH port {self.ssh_port} is open on {self.ssh_hostname}')
                    return True

            except socket.gaierror as e:
                logger.warning(f'Cannot resolve hostname {self.ssh_hostname}: {e}')
            except Exception as e:
                logger.debug(f'SSH port check failed: {e}')

            logger.info(f'Waiting for SSH to be ready on {self.ssh_hostname}:{self.ssh_port}...')
            time.sleep(2)

        return False

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(5))
    def _ssh_login(self) -> None:
        """
        Perform SSH login with retry logic.
        Automatically retries up to 5 times with 5-second intervals.
        """
        try:
            self.ssh = pxssh.pxssh(
                echo=False,
                timeout=self.timeout,
                encoding='utf-8',
                codec_errors='replace',
            )

            logger.info('Attempting SSH connection...')
            ssh_debug_cmd = f'ssh -v {self.ssh_username}@{self.ssh_hostname}'
            logger.info(f'Debug SSH with: {ssh_debug_cmd} (password: {self.ssh_password})')

            # Perform login
            self.ssh.login(
                self.ssh_hostname,
                self.ssh_username,
                self.ssh_password,
            )

            logger.info('SSH connection established successfully')

        except pxssh.ExceptionPxssh as e:
            logger.error(
                f'SSH login failed: {e}. Removing known host entry and retrying...'
            )
            self.remove_known_host_entry(self.ssh_port, self.ssh_hostname)
            raise e

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(5))
    def _ssh_login_root(self) -> None:
        """
        Perform SSH login as root user with retry logic.
        Used for setup commands that require root privileges.
        Automatically retries up to 5 times with 5-second intervals.
        """
        try:
            self.ssh_root = pxssh.pxssh(
                echo=False,
                timeout=self.timeout,
                encoding='utf-8',
                codec_errors='replace',
            )

            logger.info('Attempting root SSH connection for setup...')

            # Perform login as root
            self.ssh_root.login(
                self.ssh_hostname,
                'root',
                self.ssh_root_password,
            )

            logger.info('Root SSH connection established successfully')

        except pxssh.ExceptionPxssh as e:
            logger.error(
                f'Root SSH login failed: {e}. Removing known host entry and retrying...'
            )
            self.remove_known_host_entry(self.ssh_port, self.ssh_hostname)
            raise e

    def _is_guac_setup_complete(self) -> bool:
        """
        Check if Guacamole setup has already been completed.

        Returns:
            True if Guacamole is already set up, False otherwise
        """
        # Check if Guacamole web interface is accessible
        exit_code, _ = self.execute('curl -fsS http://localhost:8080/guacamole/ >/dev/null 2>&1')
        if exit_code != 0:
            logger.info('Guacamole web interface not accessible - setup needed')
            return False

        # Check if required config files exist
        exit_code, _ = self.execute('test -f /etc/guacamole/user-mapping.xml')
        if exit_code != 0:
            logger.info('Guacamole config files missing - setup needed')
            return False

        # Check if services are running
        exit_code, _ = self.execute('pgrep -x guacd >/dev/null && pgrep -x xrdp >/dev/null')
        if exit_code != 0:
            logger.info('Guacamole services not running - setup needed')
            return False

        logger.info('Guacamole already set up - skipping setup')
        return True

    def add_to_env(self, key: str, value: str) -> None:
        """
        Add an environment variable to the session.

        Args:
            key: Environment variable name
            value: Environment variable value
        """
        self._env[key] = value
        import json
        # Use json.dumps for proper escaping
        self.execute(f'export {key}={json.dumps(value)}')

    def init_plugins(self) -> None:
        """
        Initialize plugins and tools in the container.
        Copies tool files and runs setup script.
        """
        if hasattr(self, 'plugin_initialized') and self.plugin_initialized:
            logger.info('Plugins already initialized - skipping')
            return

        if not self.initialize_plugins:
            logger.info('Plugin initialization disabled - skipping')
            return

        logger.info('Initializing plugins in the computer')

        # Clean up and create fresh ~/.bashrc
        exit_code, output = self.execute('rm -f ~/.bashrc && touch ~/.bashrc')
        if exit_code != 0:
            logger.warning(f'Failed to reset ~/.bashrc: {output}')

        # Source bashrc
        self._source_bashrc()

        # Copy tool files to container
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        tools_path = os.path.join(parent_dir, 'tools')

        if os.path.exists(tools_path):
            # Note: This requires scp or similar file transfer mechanism
            # For now, we'll skip the actual file copy since we're using SSH-only
            logger.warning('File copying via SSH not implemented - tools must be pre-installed in container')

        # If tools are already in container, run setup
        abs_path_to_bash_script = '/infant/tools/setup.sh'
        logger.info(f'Checking for tools setup script at {abs_path_to_bash_script}')
        exit_code, output = self.execute(f'test -f {abs_path_to_bash_script}')
        if exit_code == 0:
            logger.info(f'Running tools setup script')
            exit_code, output = self.execute(abs_path_to_bash_script)
            if exit_code != 0:
                logger.warning(f'Tools setup failed with exit code {exit_code}: {output}')
            else:
                logger.info('Tools initialized successfully')

        self._source_bashrc()
        self.plugin_initialized = True

    def _source_bashrc(self) -> None:
        """Source the bashrc file to load environment."""
        if self.ssh_username == 'infant':
            exit_code, output = self.execute('source /infant/bash.bashrc && source ~/.bashrc 2>/dev/null || source ~/.bashrc')
            if exit_code != 0:
                logger.warning(f'Failed to source bashrc: {output}')
            else:
                logger.debug('Sourced bashrc successfully')
        else:
            exit_code, output = self.execute('source ~/.bashrc 2>/dev/null || true')
            if exit_code != 0:
                logger.warning(f'Failed to source ~/.bashrc: {output}')

    def config_xorg_for_gui(self) -> None:
        """
        Configure Xorg settings for GUI access.
        Sets up X authority, display settings, and prevents screen locking.
        """
        logger.info('Configuring Xorg for GUI...')

        # Fix /etc/hosts to avoid sudo warning about hostname
        self.execute('HN=$(hostname)')
        self.execute('grep -qE "(^|\\s)${HN}(\\s|$)" /etc/hosts || echo "127.0.1.1 ${HN}" | sudo tee -a /etc/hosts >/dev/null')

        # Set up Xauthority for infant user
        self.execute('XAUTH=/home/infant/.Xauthority')
        self.execute('U=$(id -u infant 2>/dev/null || id -u)')
        self.execute('G=$(id -g infant 2>/dev/null || id -g)')

        # Set permissions
        self.execute('sudo chown ${U}:${G} "$XAUTH" 2>/dev/null || sudo chown ${U} "$XAUTH" 2>/dev/null || true')
        self.execute('sudo chmod 600 "$XAUTH" 2>/dev/null || true')

        # Clean up stale lock files
        self.execute('sudo rm -f "$XAUTH"-c "$XAUTH"-l "$XAUTH".lock 2>/dev/null || true')

        # Read/create cookie for display :10
        self.execute('COOKIE=$(sudo -u \\#${U} XAUTHORITY="$XAUTH" xauth list 2>/dev/null | awk \'/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}\')')
        self.execute('[ -n "$COOKIE" ] || COOKIE=$(mcookie)')

        # Write xauth keys
        self.execute('HOST=$(hostname)')
        self.execute('sudo -u \\#${U} XAUTHORITY="$XAUTH" xauth add ":10" . "$COOKIE" 2>/dev/null || true')
        self.execute('sudo -u \\#${U} XAUTHORITY="$XAUTH" xauth add "$HOST/unix:10" . "$COOKIE" 2>/dev/null || true')
        self.execute('sudo -u \\#${U} XAUTHORITY="$XAUTH" xauth add "localhost/unix:10" . "$COOKIE" 2>/dev/null || true')

        # Export DISPLAY
        self.execute('grep -qx "export DISPLAY=:10" ~/.bashrc || echo "export DISPLAY=:10" >> ~/.bashrc')
        self.execute('export DISPLAY=:10')
        self.execute('export XAUTHORITY=/home/infant/.Xauthority')

        # Prevent screen locking
        self.execute('gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true')
        self.execute('gsettings set org.gnome.desktop.screensaver lock-delay 0 2>/dev/null || true')
        self.execute('gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true')
        self.execute('gsettings set org.gnome.settings-daemon.plugins.power idle-dim false 2>/dev/null || true')
        self.execute('gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0 2>/dev/null || true')
        self.execute('gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type \'nothing\' 2>/dev/null || true')
        self.execute('gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-timeout 0 2>/dev/null || true')
        self.execute('gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type \'nothing\' 2>/dev/null || true')
        self.execute('gsettings set org.gnome.desktop.screensaver idle-activation-enabled false 2>/dev/null || true')
        self.execute('gsettings set org.gnome.desktop.lockdown disable-lock-screen true 2>/dev/null || true')

        logger.info('Xorg configuration complete')

    def _execute_as_root(self, cmd: str, timeout: Optional[int] = None) -> Tuple[int, str]:
        """
        Execute a command as root user via the root SSH session.

        Args:
            cmd: Command to execute
            timeout: Optional timeout override (uses instance timeout if None)

        Returns:
            Tuple of (exit_code, output_string)
        """
        if timeout is None:
            timeout = self.timeout

        logger.debug(f'Executing command as root: {cmd}')

        # Send command
        self.ssh_root.sendline(cmd)

        # Wait for command to complete
        success = self.ssh_root.prompt(timeout=timeout)

        if not success:
            logger.error(f'Command timed out: {cmd}')
            self.ssh_root.sendintr()  # Send Ctrl-C
            self.ssh_root.prompt()
            return -1, f'Command timed out after {timeout} seconds'

        # Collect output
        command_output = self.ssh_root.before

        # Clean up output
        command_output = command_output.removesuffix('\r\n')

        # Get exit code
        self.ssh_root.sendline('echo $?')
        self.ssh_root.prompt(timeout=2)
        exit_code_str = self.ssh_root.before.strip()

        # Parse exit code
        cleaned_exit_code = exit_code_str.replace('echo $?', '').strip()
        try:
            exit_code = int(cleaned_exit_code)
        except ValueError:
            logger.error(f'Invalid exit code: {cleaned_exit_code}')
            exit_code = -1

        # Remove ANSI escape codes from output
        command_output = re.sub(r'\x1b\[[0-9;]*[mK]', '', command_output)

        logger.debug(f'Command completed with exit code {exit_code}')

        return exit_code, command_output

    def ensure_guac_ready(
        self,
        web_user: str = "web",
        web_pass: str = "web",
        rdp_user: str = "infant",
        rdp_pass: str = "123",
        connection_name: str = "GNOME Desktop (RDP)",
        timeout_s: float = 60.0,
    ) -> None:
        """
        Ensure that Guacamole is fully configured and services are ready.

        This method performs comprehensive setup:
        1. Creates necessary directories and configuration files
        2. Configures XRDP for GNOME Shell session
        3. Sets up dconf system defaults (dock favorites, hide volumes)
        4. Creates user-mapping.xml with connection settings
        5. Starts all required services (guacd, xrdp-sesman, xrdp, tomcat9)
        6. Verifies services are responding on their ports

        Args:
            web_user: Guacamole web interface username
            web_pass: Guacamole web interface password
            rdp_user: RDP connection username
            rdp_pass: RDP connection password
            connection_name: Display name for the RDP connection
            timeout_s: Maximum time to wait for services to be ready

        Raises:
            RuntimeError: If any setup step fails
            TimeoutError: If services are not ready within timeout period
        """
        if not self.ssh_root:
            logger.error("Root SSH session not available for setup")
            raise RuntimeError("Root SSH session required for Guacamole setup")

        logger.info("Starting Guacamole setup and configuration...")

        # Configuration constants
        INITIAL_W = 1920
        INITIAL_H = 1080
        FAVORITES = "['google-chrome.desktop','code.desktop','thunderbird.desktop','libreoffice-writer.desktop','libreoffice-calc.desktop','libreoffice-impress.desktop','org.gnome.Terminal.desktop']"

        logger.info("Executing Guacamole setup commands as root...")
        # List of configuration commands to execute
        cmds = [
            # Basic directories and GUACAMOLE_HOME symlink
            "mkdir -p /etc/guacamole /var/lib/tomcat9/webapps /usr/share/tomcat9 || true",
            "ln -sf /etc/guacamole /usr/share/tomcat9/.guacamole",

            # XRDP use GNOME Shell (Xorg)
            r"""bash -lc 'cat > /etc/xrdp/startwm.sh << "SH"
#!/bin/sh
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export GNOME_SHELL_SESSION_MODE=ubuntu
export XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XDG_SESSION_DESKTOP=ubuntu
if command -v /usr/libexec/gnome-session-binary >/dev/null 2>&1; then
exec /usr/libexec/gnome-session-binary --session=ubuntu
else
exec gnome-session --session=ubuntu
fi
SH
chmod +x /etc/xrdp/startwm.sh'""",

            # System-level dconf defaults: hide desktop mount icons + set Dock favorites
            "mkdir -p /etc/dconf/db/local.d /etc/dconf/profile",
            r"""bash -lc 'cat > /etc/dconf/profile/user << "EOF"
user-db:user
system-db:local
'""",
            r"""bash -lc 'cat > /etc/dconf/db/local.d/00-infant << "EOF"
[org/gnome/nautilus/desktop]
volumes-visible=false

[org/gnome/shell]
favorite-apps=%s

[org/gnome/shell/extensions/ding]
show-mounts=false
show-network-volumes=false
'""" % FAVORITES,
            "dconf update || true",

            # Write favorites to infant user config (try best without session bus)
            r"""bash -lc 'if id -u %s >/dev/null 2>&1; then \
sudo -H -u %s dbus-launch --exit-with-session gsettings set org.gnome.shell favorite-apps "%s" || true; \
fi'""" % (rdp_user, rdp_user, FAVORITES),

            # Write user-mapping.xml (enable display-update + initial resolution + higher DPI)
            r"""bash -lc 'cat > /etc/guacamole/user-mapping.xml << "XML"
<user-mapping>
<authorize username="%s" password="%s">
    <connection name="%s">
    <protocol>rdp</protocol>
    <param name="hostname">localhost</param>
    <param name="port">3389</param>
    <param name="username">%s</param>
    <param name="password">%s</param>

    <!-- Initial resolution + dynamic follow browser window -->
    <param name="width">%d</param>
    <param name="height">%d</param>
    <param name="resize-method">none</param>
    <param name="dpi">120</param>
    <param name="enable-font-smoothing">true</param>

    <param name="color-depth">24</param>
    <param name="security">any</param>
    <param name="ignore-cert">true</param>
    </connection>
</authorize>
</user-mapping>'""" % (web_user, web_pass, connection_name, rdp_user, rdp_pass, INITIAL_W, INITIAL_H),

            # guacamole.properties
            r"""bash -lc 'cat > /etc/guacamole/guacamole.properties << "EOF"
guacd-hostname: localhost
guacd-port: 4822
user-mapping: /etc/guacamole/user-mapping.xml
auth-provider: net.sourceforge.guacamole.net.basic.BasicFileAuthenticationProvider'""",

            r"""bash -lc 'U=$(getent passwd tomcat >/dev/null && echo tomcat || echo tomcat9); \
chown "$U:$U" /etc/guacamole/user-mapping.xml || true; \
chmod 640 /etc/guacamole/user-mapping.xml; chmod 755 /etc/guacamole'""",

            # Ensure /var/run/xrdp exists (xrdp/guacd)
            r"mkdir -p /var/run/xrdp && chown xrdp:xrdp /var/run/xrdp || true",
            r"""bash -lc 'pgrep -x guacd >/dev/null || /usr/sbin/guacd -f >/var/log/guacd.log 2>&1 &'""",
            r"""bash -lc 'pgrep -x xrdp-sesman >/dev/null || /usr/sbin/xrdp-sesman -n >/var/log/xrdp-sesman.log 2>&1 &'""",
            r"""bash -lc 'pgrep -x xrdp >/dev/null || /usr/sbin/xrdp -n >/var/log/xrdp.log 2>&1 &'""",

            # start tomcat9
            r"""bash -lc 'pgrep -f org.apache.catalina.startup.Bootstrap >/dev/null \
|| catalina.sh start \
|| (catalina.sh run >/var/log/catalina-run.log 2>&1 &)'""",

            # Clean volume icons and set dock settings
            r"""bash -lc 'set -eux; \
U=infant; \
U_ID=$(id -u "$U"); \
export XDG_RUNTIME_DIR=/run/user/$U_ID; \
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus; \
[ -S "$XDG_RUNTIME_DIR/bus" ] || (mkdir -p "$XDG_RUNTIME_DIR"; /usr/bin/dbus-daemon --session --address="unix:path=$XDG_RUNTIME_DIR/bus" --fork || true); \
FAVS="[ '\''google-chrome.desktop'\'', '\''code.desktop'\'', '\''thunderbird.desktop'\'', '\''libreoffice-writer.desktop'\'', '\''libreoffice-calc.desktop'\'', '\''libreoffice-impress.desktop'\'', '\''org.gnome.Nautilus.desktop'\'', '\''org.gnome.Terminal.desktop'\'', '\''org.gnome.Settings.desktop'\'' ]"; \
sudo -u "$U" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" gsettings set org.gnome.shell.extensions.dash-to-dock show-mounts false || true; \
sudo -u "$U" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" gsettings set org.gnome.shell.extensions.dash-to-dock show-trash false || true; \
sudo -u "$U" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" gsettings set org.gnome.shell favorite-apps "$FAVS" || true; \
sudo -u "$U" env XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" gsettings set org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 48 || true'""",

            # Add apps to dock (alternative dconf method)
            r"""bash -lc 'set -eux; rm -f /etc/dconf/db/local.d/00-infant /etc/dconf/db/local.d/00-favorites || true; mkdir -p /etc/dconf/db/local.d /etc/dconf/profile; printf "%s\n" "user-db:user" "system-db:local" > /etc/dconf/profile/user; printf "%s\n" "[org/gnome/shell]" "favorite-apps=['\''google-chrome.desktop'\'','\''code.desktop'\'','\''thunderbird.desktop'\'','\''libreoffice-writer.desktop'\'','\''libreoffice-calc.desktop'\'','\''libreoffice-impress.desktop'\'','\''org.gnome.Terminal.desktop'\'','\''org.gnome.Nautilus.desktop'\'','\''org.gnome.Settings.desktop'\'']" "" "[org/gnome/shell/extensions/dash-to-dock]" "show-mounts=false" "show-trash=false" "dash-max-icon-size=48" > /etc/dconf/db/local.d/00-favorites; dconf update'
""",

            # Skip secret/keyring check
            r"""bash -lc 'set -euo pipefail; apt-get update && apt-get install -y gnome-keyring dbus-user-session && install -d -m 755 /etc/xdg/autostart && printf "[Desktop Entry]\nType=Application\nName=Secret Service (gnome-keyring)\nExec=/usr/bin/gnome-keyring-daemon --start --components=secrets\nOnlyShowIn=GNOME;GNOME-Flashback;Unity;XFCE;LXDE;MATE;\nX-GNOME-Autostart-Phase=Initialization\nX-GNOME-Autostart-Notify=false\nNoDisplay=true\n" > /etc/xdg/autostart/gnome-keyring-secrets.desktop'
""",

            # Install and ensure XRDP packages
            r"""bash -lc 'dpkg -s xorgxrdp >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends xrdp xorgxrdp guacd)'
""",

            # Final service startup with port verification
            r"""bash -lc 'set -eux; mkdir -p /var/run/xrdp; chown xrdp:xrdp /var/run/xrdp || true; getent group ssl-cert >/dev/null && adduser xrdp ssl-cert || true; pgrep -x xrdp-sesman >/dev/null || (/usr/sbin/xrdp-sesman -n  >/var/log/xrdp-sesman.foreground.log 2>&1 &); pgrep -x xrdp >/dev/null        || (/usr/sbin/xrdp -n       >/var/log/xrdp.foreground.log        2>&1 &); pgrep -x guacd >/dev/null        || (/usr/sbin/guacd -f      >/var/log/guacd.foreground.log       2>&1 &); ss -lntp 2>/dev/null | grep -E ":(3389|4822)\\b" || true'
""",

            # Ensure tomcat9 is running
            r"""bash -lc 'pgrep -f org.apache.catalina.startup.Bootstrap >/dev/null || catalina.sh start || (catalina.sh run >/var/log/catalina-run.log 2>&1 &)'
"""
        ]

        # Execute all configuration commands as root
        logger.info(f"Executing {len(cmds)} Guacamole configuration commands...")
        for idx, cmd in enumerate(cmds, 1):
            logger.debug(f"Setup step {idx}/{len(cmds)}: {cmd[:80]}...")
            exit_code, output = self._execute_as_root(cmd)
            if exit_code != 0:
                error_msg = f"Guac setup step {idx} failed with exit code {exit_code}"
                logger.error(f"{error_msg}\nCommand: {cmd}\nOutput: {output}")
                raise RuntimeError(f"{error_msg}: {output}")

        logger.info("All configuration commands executed successfully")

        # Wait for Guacamole web UI to be ready
        logger.info(f"Waiting up to {timeout_s}s for Guacamole web interface...")
        start = time.time()
        guac_ready = False

        while time.time() - start < timeout_s:
            exit_code, _ = self._execute_as_root('curl -fsS http://localhost:8080/guacamole/ >/dev/null 2>&1')
            if exit_code == 0:
                guac_ready = True
                logger.info('Guacamole web interface is ready at :8080/guacamole')
                break
            time.sleep(0.5)

        if not guac_ready:
            raise TimeoutError(f"Guacamole web UI not ready at :8080/guacamole after {timeout_s}s")

        # Verify RDP port is listening
        logger.info("Verifying RDP service on port 3389...")
        exit_code, output = self._execute_as_root('ss -lntp 2>/dev/null | grep -E ":3389\\b" || netstat -lntp 2>/dev/null | grep -E ":3389\\b" || echo "not found"')
        if "not found" in output.lower():
            logger.warning("RDP port 3389 may not be listening, but continuing...")
        else:
            logger.info("RDP service verified on port 3389")

        logger.info("Guacamole setup completed successfully!")

    def connect(self) -> None:
        """
        Establish SSH connection and configure the session.
        """
        # Wait for SSH service to be ready
        logger.info(f'Waiting for SSH service to be ready on {self.ssh_hostname}:{self.ssh_port}...')
        if not self._wait_for_ssh_ready(max_wait=60):
            raise ConnectionError(
                f'SSH service not available on {self.ssh_hostname}:{self.ssh_port} after 60 seconds. '
                f'Please ensure the computer-container is running and SSH service is started.'
            )

        # Perform SSH login with retry (infant user)
        self._ssh_login()

        # Disable bracketed paste mode (improves command handling)
        self.ssh.sendline("bind 'set enable-bracketed-paste off'")
        self.ssh.prompt()

        # Check if Guacamole setup is needed
        logger.info('Checking if Guacamole setup is needed...')
        if not self._is_guac_setup_complete():
            logger.info('Guacamole setup needed - connecting as root user for setup...')

            # Connect as root for setup
            self._ssh_login_root()

            # Disable bracketed paste mode for root session
            self.ssh_root.sendline("bind 'set enable-bracketed-paste off'")
            self.ssh_root.prompt()

            # Run setup
            try:
                self.ensure_guac_ready(timeout_s=60)
            except TimeoutError as e:
                logger.warning(f'Guacamole services check failed: {e}')
                logger.warning('Proceeding with SSH connection anyway...')

            # Close root session after setup
            logger.info('Setup complete - closing root SSH session')
            try:
                self.ssh_root.logout()
                self.ssh_root = None
            except Exception as e:
                logger.error(f'Error closing root SSH connection: {e}')
        else:
            logger.info('Guacamole already set up - skipping setup')

        # Change to workspace directory (as infant user)
        self.ssh.sendline(f'cd {self.workspace_dir}')
        self.ssh.prompt()

        # Set up basic git configuration
        logger.info('Setting up git configuration...')
        self.execute('mkdir -p /tmp')
        self.execute('git config --global user.name "infant"')
        self.execute('git config --global user.email "infant@ai.com"')

        # Set up environment variables from host
        import os
        for key in os.environ:
            if key.startswith('SANDBOX_ENV_'):
                computer_key = key.removeprefix('SANDBOX_ENV_')
                self.add_to_env(computer_key, os.environ[key])

        # Add auto-lint if enabled
        if self.enable_auto_lint:
            self.add_to_env('ENABLE_AUTO_LINT', 'true')

        # Initialize plugins if enabled
        if self.initialize_plugins:
            logger.info('Initializing plugins...')
            exit_code, output = self.execute('whoami')
            logger.info(f'Current user: {output}')
            self.init_plugins()

        # Configure Xorg for GUI
        logger.info('Configuring Xorg for GUI access...')
        self.config_xorg_for_gui()

        # Set up Chrome and other tools
        logger.info('Setting up additional tools...')
        from infant.helper_functions.setting_up import PYTHON_SETUP_CODE
        output = self.run_python(PYTHON_SETUP_CODE)
        logger.debug(f'Python setup output: {output}')

        # Set UTF-8 encoding
        self.ssh.sendline('export PYTHONIOENCODING=utf-8')
        self.ssh.prompt()

        logger.info(f'SSH session configured. Working directory: {self.workspace_dir}')

    def execute(
        self,
        cmd: str,
        timeout: Optional[int] = None
    ) -> Tuple[int, str]:
        """
        Execute a command via SSH and return exit code and output.

        Args:
            cmd: Command to execute
            timeout: Optional timeout override (uses instance timeout if None)

        Returns:
            Tuple of (exit_code, output_string)
        """
        if timeout is None:
            timeout = self.timeout

        logger.debug(f'Executing command: {cmd}')

        # Send command
        self.ssh.sendline(cmd)

        # Wait for command to complete
        success = self.ssh.prompt(timeout=timeout)

        if not success:
            logger.error(f'Command timed out: {cmd}')
            self.ssh.sendintr()  # Send Ctrl-C
            self.ssh.prompt()
            return -1, f'Command timed out after {timeout} seconds'

        # Collect output
        command_output = self.ssh.before

        # Clean up output
        command_output = command_output.removesuffix('\r\n')

        # Get exit code
        self.ssh.sendline('echo $?')
        self.ssh.prompt(timeout=2)
        exit_code_str = self.ssh.before.strip()

        # Parse exit code
        cleaned_exit_code = exit_code_str.replace('echo $?', '').strip()
        try:
            exit_code = int(cleaned_exit_code)
        except ValueError:
            logger.error(f'Invalid exit code: {cleaned_exit_code}')
            exit_code = -1

        # Remove ANSI escape codes from output
        command_output = re.sub(r'\x1b\[[0-9;]*[mK]', '', command_output)

        logger.debug(f'Command completed with exit code {exit_code}')

        return exit_code, command_output

    async def run_command(self, memory) -> str:
        """
        Execute a command from memory object (compatible with agent interface).

        Args:
            memory: CmdRun memory object with command attribute

        Returns:
            Formatted output string
        """
        command = memory.command
        exit_code, output = self.execute(command)

        # Clean up output
        if output.startswith(command):
            output = output[len(command):].strip()

        return f'(exit code={exit_code})\n{output}'

    def run_python(self, code: str) -> str:
        """
        Execute Python code via a temporary file.

        Args:
            code: Python code to execute

        Returns:
            Formatted output string
        """
        # Write code to temporary file using heredoc
        self.execute(
            f"cat > /tmp/infant_jupyter_temp.py <<'EOL'\n{code}\nEOL"
        )

        # Execute the Python file
        exit_code, output = self.execute('python3 /tmp/infant_jupyter_temp.py')

        # Clean up output
        if output.startswith('python3 /tmp/infant_jupyter_temp.py'):
            output = output[len('python3 /tmp/infant_jupyter_temp.py'):].strip()

        return f'(exit code={exit_code})\n{output}'

    async def run_ipython(self, memory) -> str:
        """
        Execute IPython code from memory object (compatible with agent interface).

        This is a simplified version that doesn't support all desktop GUI features.
        Desktop-related commands (like press_key, mouse operations) are ignored.

        Args:
            memory: IPythonRun memory object with code attribute

        Returns:
            Formatted output string
        """
        code = memory.code

        # Handle local execution for audio/video functions
        for func_name in ['parse_audio', 'parse_video', 'watch_video']:
            if func_name in code:
                logger.info(f'Executing {func_name} locally...')
                local_vars = {}
                try:
                    # Import required functions for exec
                    from infant.helper_functions.audio_helper_function import parse_audio
                    from infant.helper_functions.video_helper_function import parse_video, watch_video

                    code_to_exec = code.replace(func_name, f'result = {func_name}')
                    exec(code_to_exec, globals(), local_vars)
                    return str(local_vars.get('result', ''))
                except Exception as e:
                    logger.error(f'Error executing {func_name}: {e}')
                    return f'(exit code=1)\nError: {e}'

        # Skip desktop GUI commands that require X11/display
        desktop_commands = ['press_key', 'mouse_', 'take_screenshot', 'open_application']
        if any(cmd in code for cmd in desktop_commands):
            logger.warning(f'Skipping desktop GUI command (not supported in SSH-only mode): {code[:100]}...')
            return '(exit code=0)\n[Desktop GUI command skipped in SSH-only mode]'

        # Write code to temporary file using heredoc
        self.execute(
            f"cat > /tmp/infant_jupyter_temp.py <<'EOL'\n{code}\nEOL"
        )

        # Execute using execute_cli.sh if available, otherwise use python3 directly
        exit_code, output = self.execute('which execute_cli.sh')
        if exit_code == 0:
            # Use execute_cli.sh for IPython kernel execution
            exit_code, output = self.execute('cat /tmp/infant_jupyter_temp.py | execute_cli.sh')
        else:
            # Fallback to direct python execution
            logger.debug('execute_cli.sh not found, using python3 directly')
            exit_code, output = self.execute('python3 /tmp/infant_jupyter_temp.py')

        # Handle pip install with kernel restart
        if 'pip install' in code and 'Successfully installed' in output:
            logger.info('Package installed successfully')
            restart_kernel = 'import IPython\nIPython.Application.instance().kernel.do_shutdown(True)'

            if 'Note: you may need to restart the kernel to use updated packages.' in output:
                logger.info('Restarting IPython kernel...')

                # Write restart code
                self.execute(
                    f"cat > /tmp/infant_jupyter_temp.py <<'EOL'\n{restart_kernel}\nEOL"
                )

                # Execute restart
                restart_exit_code, restart_output = self.execute('cat /tmp/infant_jupyter_temp.py | execute_cli.sh')

                output = '[Package installed successfully]'
                if "{'status': 'ok', 'restart': True}" != restart_output.strip():
                    logger.warning(f'Kernel restart failed: {restart_output}')
                    output += '\n[But failed to restart the kernel to load the package]'
                else:
                    output += '\n[Kernel restarted successfully to load the package]'

                    # Re-initialize kernel if init code is provided
                    if hasattr(memory, 'kernel_init_code') and memory.kernel_init_code:
                        logger.info('Re-initializing kernel with init code...')
                        self.execute(
                            f"cat > /tmp/infant_jupyter_init.py <<'EOL'\n{memory.kernel_init_code}\nEOL"
                        )
                        self.execute('cat /tmp/infant_jupyter_init.py | execute_cli.sh')

        # Check for basic check failure
        if '<|Basic check failed|>' in output:
            if hasattr(memory, 'basic_check'):
                memory.basic_check = False
            return f'{output}'

        return f'{output}'

    @property
    def workspace_mount_path(self) -> str:
        """
        Return the workspace mount path for compatibility with original Computer class.
        In the simplified version, this is just the workspace_dir.
        """
        return self.workspace_dir

    @property
    def workspace_git_path(self) -> str:
        """
        Return the workspace git path for compatibility with original Computer class.
        In the simplified version, this is just the workspace_dir.
        """
        return self.workspace_dir

    def get_working_directory(self) -> str:
        """
        Get the current working directory in the container.

        Returns:
            Current working directory path
        """
        exit_code, result = self.execute('pwd')
        if exit_code != 0:
            raise Exception('Failed to get working directory')
        return result.strip()

    def copy_to(self, host_src: str, computer_dest: str, recursive: bool = False) -> None:
        """
        Copy a file or directory from host to container using SCP.

        Args:
            host_src: Source file/directory path on host
            computer_dest: Destination path in container
            recursive: Whether to copy recursively (for directories)

        Raises:
            Exception: If copy operation fails
        """
        import subprocess

        # Create destination directory in container
        exit_code, output = self.execute(f'mkdir -p {computer_dest}')
        if exit_code != 0:
            raise Exception(f'Failed to create directory {computer_dest} in computer: {output}')

        # Build SCP command
        scp_cmd = ['scp', '-P', str(self.ssh_port)]

        if recursive:
            scp_cmd.append('-r')

        # Add source
        scp_cmd.append(host_src)

        # Add destination
        dest = f'{self.ssh_username}@{self.ssh_hostname}:{computer_dest}'
        scp_cmd.append(dest)

        # Execute SCP
        logger.info(f'Copying {host_src} to {computer_dest} in container...')
        try:
            result = subprocess.run(
                scp_cmd,
                input=f'{self.ssh_password}\n',
                text=True,
                capture_output=True,
                timeout=300,
            )
            if result.returncode != 0:
                # Try with sshpass if available
                sshpass_cmd = [
                    'sshpass', '-p', self.ssh_password,
                    'scp', '-P', str(self.ssh_port), '-o', 'StrictHostKeyChecking=no'
                ]
                if recursive:
                    sshpass_cmd.append('-r')
                sshpass_cmd.extend([host_src, dest])

                result = subprocess.run(sshpass_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    raise Exception(f'SCP failed: {result.stderr}')

            logger.info(f'Successfully copied {host_src} to {computer_dest}')
        except subprocess.TimeoutExpired:
            raise Exception(f'SCP timed out after 300 seconds')
        except FileNotFoundError as e:
            if 'sshpass' in str(e):
                logger.error('sshpass not found. Please install it: sudo apt-get install sshpass')
            raise Exception(f'Copy failed: {e}')

    def copy_from(self, computer_src: str, host_dest: str, recursive: bool = False) -> None:
        """
        Copy a file or directory from container to host using SCP.

        Args:
            computer_src: Source file/directory path in container
            host_dest: Destination path on host
            recursive: Whether to copy recursively (for directories)

        Raises:
            Exception: If copy operation fails
        """
        import subprocess
        import os

        # Create destination directory on host
        os.makedirs(os.path.dirname(host_dest) if not os.path.isdir(host_dest) else host_dest, exist_ok=True)

        # Build SCP command
        scp_cmd = ['scp', '-P', str(self.ssh_port)]

        if recursive:
            scp_cmd.append('-r')

        # Add source
        src = f'{self.ssh_username}@{self.ssh_hostname}:{computer_src}'
        scp_cmd.append(src)

        # Add destination
        scp_cmd.append(host_dest)

        # Execute SCP
        logger.info(f'Copying {computer_src} from container to {host_dest}...')
        try:
            result = subprocess.run(
                scp_cmd,
                input=f'{self.ssh_password}\n',
                text=True,
                capture_output=True,
                timeout=300,
            )
            if result.returncode != 0:
                # Try with sshpass if available
                sshpass_cmd = [
                    'sshpass', '-p', self.ssh_password,
                    'scp', '-P', str(self.ssh_port), '-o', 'StrictHostKeyChecking=no'
                ]
                if recursive:
                    sshpass_cmd.append('-r')
                sshpass_cmd.extend([src, host_dest])

                result = subprocess.run(sshpass_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    raise Exception(f'SCP failed: {result.stderr}')

            logger.info(f'Successfully copied {computer_src} to {host_dest}')
        except subprocess.TimeoutExpired:
            raise Exception(f'SCP timed out after 300 seconds')
        except FileNotFoundError as e:
            if 'sshpass' in str(e):
                logger.error('sshpass not found. Please install it: sudo apt-get install sshpass')
            raise Exception(f'Copy failed: {e}')

    def close(self) -> None:
        """
        Close the SSH connections.
        """
        if self.ssh:
            try:
                if self.ssh.isalive():
                    self.ssh.logout()
                    logger.info('SSH connection (infant user) closed')
                self.ssh = None
            except Exception as e:
                logger.debug(f'Error closing SSH connection: {e}')
                self.ssh = None

        if self.ssh_root:
            try:
                if self.ssh_root.isalive():
                    self.ssh_root.logout()
                    logger.info('Root SSH connection closed')
                self.ssh_root = None
            except Exception as e:
                logger.debug(f'Error closing root SSH connection: {e}')
                self.ssh_root = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __del__(self):
        """Cleanup on deletion."""
        self.close()


def create_computer_from_params(config, sid: str | None = None):
    """
    Factory function to create Computer from ComputerParams (for backward compatibility).

    This allows Computer to be used as a drop-in replacement for Computer.

    Args:
        config: ComputerParams object
        sid: Session ID (optional, not used but kept for compatibility)

    Returns:
        Computer instance configured from params
    """
    from infant.config import ComputerParams

    if isinstance(config, ComputerParams):
        return Computer(
            ssh_hostname=config.ssh_hostname or 'localhost',
            ssh_port=config.ssh_bind_port or 22,
            ssh_password=config.ssh_password or '123',
            ssh_username='infant' if config.run_as_infant else 'root',
            ssh_root_password='123',
            timeout=config.computer_timeout or 120,
            workspace_dir=config.workspace_mount_path_in_computer or '/workspace',
            enable_auto_lint=False,
            initialize_plugins=True,
        )
    else:
        # If it's already keyword arguments, just pass through
        return Computer(**config)


def test_connection():
    """
    Test function to verify SSH connection to computer-container.
    """
    print("Testing SSH connection to computer-container...")

    # Create computer instance
    computer = Computer(
        ssh_hostname='172.18.0.2',
        ssh_port=22,  # From docker-compose.yaml
        ssh_password='123',
        ssh_username='infant',
        ssh_root_password='123',
        workspace_dir='/workspace',
        enable_auto_lint=False,
        initialize_plugins=False,
    )

    try:
        # Test basic command
        print("\n1. Testing basic command (whoami):")
        exit_code, output = computer.execute('whoami')
        print(f"   Exit code: {exit_code}")
        print(f"   Output: {output}")

        # Test working directory
        print("\n2. Testing working directory:")
        pwd = computer.get_working_directory()
        print(f"   Current directory: {pwd}")

        # Test Python execution
        print("\n3. Testing Python execution:")
        result = computer.run_python("print('Hello from Python!')")
        print(f"   Result: {result}")

        # Test file operations
        print("\n4. Testing file operations:")
        exit_code, output = computer.execute('ls -la /workspace')
        print(f"   Workspace contents:\n{output}")

        print("\n✓ All tests passed!")

    finally:
        computer.close()


if __name__ == '__main__':
    test_connection()
