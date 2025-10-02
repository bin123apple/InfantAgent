import os
import re
import time
import json
import atexit
import docker
import socket
import tarfile
import pexpect
import tempfile
import requests
import subprocess
from glob import glob
from pathlib import Path
from pexpect import pxssh
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed
from infant.util.exceptions import ComputerInvalidBackgroundCommandError
from infant.util.logger import infant_logger as logger
from infant.config import ComputerParams
from infant.prompt.tools_prompt import tool_trace_code, tool_filter_bash_code
from infant.agent.memory.memory import IPythonRun, CmdRun
from infant.helper_functions.audio_helper_function import parse_audio # for exec()
from infant.helper_functions.video_helper_function import parse_video, watch_video # for exec()

class Computer:
    instance_id: str
    container_image: str
    container_name_prefix = 'infant-computer-'
    container_name: str
    container: docker.models.containers.Container
    docker_client: docker.DockerClient

    _ssh_password: str
    _ssh_port: int
    ssh: pxssh.pxssh
    _env: dict[str, str] = {}

    cur_background_id = 0

    def __init__(
        self,
        config: ComputerParams,
        sid: str | None = None,
    ):

        # Initialize the computer properties
        self.trace = False # Whether to trace the code execution, there might be some bugs. No time to fix this for now.
        self.timeout = config.computer_timeout
        # self.instance_id = (sid or '') + str(uuid.uuid4())
        self.consistant_computer = config.consistant_computer
        self.instance_id = config.instance_id # Try constant instance_id
        self.container_image = config.computer_container_image
        self.workspace_git_path = config.workspace_git_path
        self.container_name = self.container_name_prefix + self.instance_id
        self.gui_port = config.gui_port if config.gui_port else self.find_available_tcp_port()
        self.nvidia_driver = config.nvidia_driver
        self._ssh_password = config.ssh_password
        self._ssh_port = 58673 if self.consistant_computer else self.find_available_tcp_port()
        self.user_id = config.computer_user_id
        self.computer_user_id = config.computer_user_id
        self.run_as_infant = config.run_as_infant
        self.intermediate_results_dir = config.intermediate_results_dir
        self.computer_workspace_dir = config.workspace_mount_path_in_computer
        self.ssh_hostname = config.ssh_hostname
        self.use_host_network = config.use_host_network
        self.workspace_mount_path = config.workspace_mount_path
        self.cache_dir = config.cache_dir
        self.render_type = config.render_type
        self.ssh_bind_port = config.ssh_bind_port if config.ssh_bind_port else self.find_available_tcp_port()
        self.nomachine_bind_port = config.nomachine_bind_port if config.nomachine_bind_port else self.find_available_tcp_port()
        self.nvidia_visible_devices = config.nvidia_visible_devices
        self.text_only_docker = config.text_only_docker
        self.volumes = self.set_volumes()
        logger.info(f'SSHBox is running as {"infant" if self.run_as_infant else "root"} user with USER_ID={self.user_id} in the computer')
        params = {
            'text_only_docker': self.text_only_docker,
            'trace': self.trace,
            'instance_id': self.instance_id,
            'container_image': self.container_image,
            'container_name': self.container_name,
            'gui_port': self.gui_port,
            'computer_workspace_dir': self.computer_workspace_dir,
            'ssh_hostname': self.ssh_hostname,
            'ssh_port': self._ssh_port,
            'ssh_password': self._ssh_password,
            'ssh_bind_port': self.ssh_bind_port,
            'nomachine_bind_port': self.nomachine_bind_port,
            'use_host_network': self.use_host_network,
            'workspace_mount_path': self.workspace_mount_path,
            'cache_dir': self.cache_dir,
            'render_type': self.render_type,
            'nvidia_visible_devices': self.nvidia_visible_devices,
            'computer_user_id': self.computer_user_id,
            'computer_workspace_dir': self.computer_workspace_dir,
            'computer_container_image': self.container_image,
            'computer_container_name': self.container_name,
            'computer_container_name_prefix': self.container_name_prefix,
            'text_only_docker': self.text_only_docker,
        }
        # Create a string of non-None parameters for logging
        logger.info(f'Initializing the Computer with the following parameters:')
        for key in params:
            logger.info(f"{key}: {params[key]}")
        
        # connect to docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as ex:
            logger.exception(f'Error creating docker client. Please check Docker is running.',exc_info=False,)
            raise ex        

        # check if the container exists
        try:
            docker.DockerClient().containers.get(self.container_name)
            self.is_initial_session = False
        except docker.errors.NotFound:
            self.is_initial_session = True
            logger.info('Detected initial session.')
            
        if self.is_initial_session:
            # create mount folder
            os.makedirs(self.workspace_mount_path, exist_ok=True)
            logger.info(f'Created workspace mount path: {self.workspace_mount_path}')
            
            logger.info('Creating new Docker container')
            n_tries = 5
            while n_tries > 0:
                try:
                    self.restart_docker_container()
                    break
                except Exception as e:
                    logger.exception('Failed to start Docker container, retrying...', exc_info=False)
                    n_tries -= 1
                    if n_tries == 0:
                        raise e
                    time.sleep(5)
            self.setup_user()
            
            # ssh login to the container
            try:
                self.start_ssh_session()
            except Exception as e:
                self.close()
                raise e     
                   
            # set up some basic settings and the cleanup function
            self.execute('mkdir -p /tmp')
            self.execute('git config --global user.name "infant"')
            self.execute('git config --global user.email "infant@ai.com"')
            atexit.register(self.close)
            
            # set up the environment variables
            for key in os.environ:
                if key.startswith('SANDBOX_ENV_'):
                    computer_key = key.removeprefix('SANDBOX_ENV_')
                    self.add_to_env(computer_key, os.environ[key])
            if config.enable_auto_lint:
                self.add_to_env('ENABLE_AUTO_LINT', 'true')
                
            # Initialize plugins
            exit_code, output = self.execute('whoami') # DEBUG: Check current user
            logger.info(f'Current user: {output}') # DEBUG: Check current user
            self.initialize_plugins: bool = config.initialize_plugins
            if self.initialize_plugins: # Initialize plugins & Tools
                self.init_plugins()
            
            # GPU driver initialization # Move to the dockerfile
            if self.nvidia_driver == "Tesla":
                logger.info("Initializing Tesla GPU driver")
                exec_response = self.container.exec_run(
                    "bash /home/Tesla-XorgDisplaySettingAuto.sh",
                    stream=True 
                )

                for line in exec_response.output:
                    print(line.decode('utf-8'), end='')
            elif self.nvidia_driver == "GeForce":
                logger.warning("GeForce GPU type not supported by the automatic script. Please configure manually.")
            else:
                logger.warning("Current GPU type not supported by the automatic script. Please configure manually.")
        else:
            self.container = self.docker_client.containers.get(self.container_name)
            logger.info('Using existing Docker container')
            self.start_docker_container()
            
            # ssh login to the container
            try:
                self.start_ssh_session()
            except Exception as e:
                self.close()
                raise e

        # auto login to the nomachine
        # self.automate_nomachine_login(initial_session = self.is_initial_session)
        info = self.ensure_and_login_guac(
            base_url=f"http://localhost:{self.gui_port}/guacamole",  # 例如 4443
            web_user="web", web_pass="web",
            rdp_user="infant", rdp_pass="123",
            connection_name="GNOME Desktop (RDP)",
        )
        print(info["client_url"] or info["index_url"])
        
        self.config_xorg_for_gui()

        
    def init_plugins(self):
        """Load a plugin into the computer."""

        if hasattr(self, 'plugin_initialized') and self.plugin_initialized:
            return

        if self.initialize_plugins:
            logger.info('Initializing plugins in the computer')

            # clean-up ~/.bashrc and touch ~/.bashrc
            exit_code, output = self.execute('rm -f ~/.bashrc && touch ~/.bashrc')

            self._source_bashrc()

            # copy over the files
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            tools_path = os.path.join(parent_dir, 'tools')
            self.copy_to(
                tools_path, '/infant/tools', recursive=True
            )
            logger.info(
                f'Copied files from [{tools_path}] to "/infant/tools" inside computer.'
            )

            # Execute the bash script
            abs_path_to_bash_script = os.path.join(
                '/infant/tools', 'setup.sh'
            )
            logger.info(
                f'Initializing tools by executing [{abs_path_to_bash_script}] in the computer.'
            )
            exit_code, output = self.execute(abs_path_to_bash_script, stream=True)
            if exit_code != 0:
                raise RuntimeError(
                    f'Failed to initialize tools with exit code {exit_code} and output: {output}'
                )
            logger.info(f'Tools initialized successfully.')
        else:
            logger.info('Skipping plugin initialization in the computer')

        self._source_bashrc()

        self.plugin_initialized = True

    def add_to_env(self, key: str, value: str):
        self._env[key] = value
        # Note: json.dumps gives us nice escaping for free
        self.execute(f'export {key}={json.dumps(value)}')

    def setup_user(self):
        # Make users sudoers passwordless
        # TODO(computer): add this line in the Dockerfile for next minor version of docker image
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', r"echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"],
            workdir=self.computer_workspace_dir,
            environment=self._env,
        )
        if exit_code != 0:
            raise Exception(
                f'Failed to make all users passwordless sudoers in computer: {logs}'
            )

        # Check if the infant user exists
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', 'id -u infant'],
            workdir=self.computer_workspace_dir,
            environment=self._env,
        )
        if exit_code == 0:
            # User exists, delete it
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', 'userdel -r infant'],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to remove infant user in computer: {logs}')

        if self.run_as_infant:
            # Create the infant user
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f'useradd -rm -d /home/infant -s /bin/bash -g root -G sudo -u {self.user_id} infant',
                ],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to create infant user in computer: {logs}')
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f"echo 'infant:{self._ssh_password}' | chpasswd",
                ],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to set password in computer: {logs}')

            # chown the home directory
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', 'chown infant:root /home/infant'],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(
                    f'Failed to chown home directory for infant in computer: {logs}'
                )
            # check the miniforge3 directory exist
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', '[ -d "/infant/miniforge3" ] && exit 0 || exit 1'],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(
                    f'An error occurred while checking if miniforge3 directory exists: {logs}'
                )
            # chown the miniforge3
            exit_code, logs = self.container.exec_run(
                ['/bin/bash', '-c', 'chown -R infant:root /infant/miniforge3'],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(
                    f'Failed to chown miniforge3 directory for infant in computer: {logs}'
                )
            exit_code, logs = self.container.exec_run(
                [
                    '/bin/bash',
                    '-c',
                    f'chown infant:root {self.computer_workspace_dir}',
                ],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                # This is not a fatal error, just a warning
                logger.warning(
                    f'Failed to chown workspace directory for infant in computer: {logs}. But this should be fine if the {self.computer_workspace_dir=} is mounted by the app docker container.'
                )
        else:
            exit_code, logs = self.container.exec_run(
                # change password for root
                ['/bin/bash', '-c', f"echo 'root:{self._ssh_password}' | chpasswd"],
                workdir=self.computer_workspace_dir,
                environment=self._env,
            )
            if exit_code != 0:
                raise Exception(f'Failed to set password for root in computer: {logs}')
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', "echo 'infant-computer' > /etc/hostname"],
            workdir=self.computer_workspace_dir,
            environment=self._env,
        )
        
        exit_code, logs = self.container.exec_run("sed -i '$a\\PermitRootLogin yes' /etc/ssh/sshd_config")
        if exit_code != 0:
            raise Exception(f'Failed to set PermitRootLogin in computer: {logs}')

    def remove_known_host_entry(self, port, hostname):
        home = Path.home()
        command = f'ssh-keygen -f "{home}/.ssh/known_hosts" -R "[localhost]:{port}"'
        try:
            result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            logger.info(f"result.stdout while trying to remove known host port {port}", result.stdout)
            logger.info(f"Successfully removed known host port: {port}.")
        except subprocess.CalledProcessError as e:
            logger.info(f"Error while trying to delete known host port {port}:", e.stderr)
        
        ### For root user    
        # try:
        #     # Add host key to known_hosts to avoid interactive prompt
        #     subprocess.run(
        #         ["ssh-keyscan", "-p", port, hostname],
        #         stdout=open(f"{os.path.expanduser('~')}/.ssh/known_hosts", "a"),
        #         stderr=subprocess.DEVNULL,
        #     )
        # except Exception as e:
        #     logger.exception(f'Failed to add host key to known_hosts: {e}', exc_info=False)
            
    # Use the retry decorator, with a maximum of 5 attempts and a fixed wait time of 5 seconds between attempts
    @retry(stop=stop_after_attempt(5), wait=wait_fixed(5))
    def __ssh_login(self):
        try:
            self.ssh = pxssh.pxssh(
                echo=False,
                timeout=self.timeout,
                encoding='utf-8',
                codec_errors='replace',
            )
            hostname = self.ssh_hostname
            username = 'infant' if self.run_as_infant else 'root'
            password_msg = f"using the password '{self._ssh_password}'"
            logger.info('Connecting to SSH session...')
            ssh_cmd = f'`ssh -v -p {self._ssh_port} {username}@{hostname}`'
            logger.info(
                f'You can debug the SSH connection by running: {ssh_cmd} {password_msg}'
            )
            # time.sleep(5000) # DEBUG: Check the SSH connection
            self.ssh.login(hostname, username, self._ssh_password, port=self._ssh_port)
            logger.info('Connected to SSH session')
        except pxssh.ExceptionPxssh as e:
            logger.exception(
                f'Failed to login to SSH session, reason: {e}, will remove known host entry for port {self._ssh_port} and try again.', exc_info=False
            )
            # time.sleep(10000000) # DEBUG: Check the SSH connection
            self.remove_known_host_entry(self._ssh_port, hostname)
            raise e

    def start_ssh_session(self):
        self.__ssh_login()
        self.ssh.sendline("bind 'set enable-bracketed-paste off'")
        self.ssh.prompt()
        
        # cd to workspace
        self.ssh.sendline(f'cd {self.computer_workspace_dir}')
        self.ssh.prompt()
    
    def ensure_guac_ready(
        self, *,
        web_user: str = "web",
        web_pass: str = "web",
        rdp_user: str = "infant",
        rdp_pass: str = "123",
        connection_name: str = "GNOME Desktop (RDP)",
        timeout_s: float = 15.0,
    ):
        """在容器内自动配置 Guacamole（文件认证）并确保相关服务就绪。"""
        # 目标：GNOME Shell、常用 Dock、跳过色彩管理弹窗、Guac 初始 1280x1080 + 动态跟随
        INITIAL_W = 1920
        INITIAL_H = 1080
        FAVORITES = "['google-chrome.desktop','code.desktop','thunderbird.desktop','libreoffice-writer.desktop','libreoffice-calc.desktop','libreoffice-impress.desktop','org.gnome.Terminal.desktop']"
        self.execute('sudo id infant >/dev/null 2>&1 || sudo useradd -m -s /bin/bash infant')
        cmds = [
            # 0) 基础目录与 GUACAMOLE_HOME symlink
            "mkdir -p /etc/guacamole /var/lib/tomcat9/webapps /usr/share/tomcat9 || true",
            "ln -sf /etc/guacamole /usr/share/tomcat9/.guacamole",

            # 1) XRDP 使用 GNOME Shell（Xorg）
            r"""bash -lc 'cat > /etc/xrdp/startwm.sh << "SH"
    #!/bin/sh
    unset DBUS_SESSION_BUS_ADDRESS
    unset XDG_RUNTIME_DIR
    export GNOME_SHELL_SESSION_MODE=ubuntu
    export XDG_CURRENT_DESKTOP=ubuntu:GNOME
    export XDG_SESSION_DESKTOP=ubuntu
    # Ubuntu 22.04: binary 路径如下；若不存在，后备为 gnome-session
    if command -v /usr/libexec/gnome-session-binary >/dev/null 2>&1; then
    exec /usr/libexec/gnome-session-binary --session=ubuntu
    else
    exec gnome-session --session=ubuntu
    fi
    SH
    chmod +x /etc/xrdp/startwm.sh'""",

            # 2) 系统级 dconf 默认值：隐藏桌面挂载图标 + 设定 Dock 收藏
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

            # 3) （尽量）把收藏写入 infant 的用户配置（没有会话总线也尽力一把）
            r"""bash -lc 'if id -u %s >/dev/null 2>&1; then \
    sudo -H -u %s dbus-launch --exit-with-session gsettings set org.gnome.shell favorite-apps "%s" || true; \
    fi'""" % (rdp_user, rdp_user, FAVORITES),

#             # 4) polkit：允许 infant 执行 colord 相关动作（避免色彩管理弹窗）
#             r"""bash -lc '
#             set -e
# mkdir -p /etc/polkit-1/rules.d
# cat > /etc/polkit-1/rules.d/45-colord-nopass.rules << "EOF"
#     polkit.addRule(function(action, subject) {
#     if (subject.user == "%s" &&
#         (action.id == "org.freedesktop.color-manager.create-device" ||
#         action.id == "org.freedesktop.color-manager.create-profile" ||
#         action.id == "org.freedesktop.color-manager.modify-device" ||
#         action.id == "org.freedesktop.color-manager.modify-profile" ||
#         action.id == "org.freedesktop.color-manager.set-system-wide")) {
#         return polkit.Result.YES;
#     }
#     });'""" % rdp_user,

            # 5) 写 user-mapping.xml（启用 display-update + 初始 1280×1080 + 提升 DPI）
            r"""bash -lc 'cat > /etc/guacamole/user-mapping.xml << "XML"
    <user-mapping>
    <authorize username="%s" password="%s">
        <connection name="%s">
        <protocol>rdp</protocol>
        <param name="hostname">localhost</param>
        <param name="port">3389</param>
        <param name="username">%s</param>
        <param name="password">%s</param>

        <!-- 初始分辨率 + 动态跟随浏览器窗口 -->
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

            # 6) guacamole.properties（文件认证 + guacd）
            r"""bash -lc 'cat > /etc/guacamole/guacamole.properties << "EOF"
    guacd-hostname: localhost
    guacd-port: 4822
    user-mapping: /etc/guacamole/user-mapping.xml
    auth-provider: net.sourceforge.guacamole.net.basic.BasicFileAuthenticationProvider'""",

            # 7) 权限（tomcat/tomcat9 二选一）
            r"""bash -lc 'U=$(getent passwd tomcat >/dev/null && echo tomcat || echo tomcat9); \
    chown "$U:$U" /etc/guacamole/user-mapping.xml || true; \
    chmod 640 /etc/guacamole/user-mapping.xml; chmod 755 /etc/guacamole'""",

            # 8) 确保运行目录与进程（xrdp/guacd）
            r"mkdir -p /var/run/xrdp && chown xrdp:xrdp /var/run/xrdp || true",
            r"""bash -lc 'pgrep -x guacd >/dev/null || /usr/sbin/guacd -f >/var/log/guacd.log 2>&1 &'""",
            r"""bash -lc 'pgrep -x xrdp-sesman >/dev/null || /usr/sbin/xrdp-sesman -n >/var/log/xrdp-sesman.log 2>&1 &'""",
            r"""bash -lc 'pgrep -x xrdp >/dev/null || /usr/sbin/xrdp -n >/var/log/xrdp.log 2>&1 &'""",

            # 9) 兜底启动 Tomcat（/guacamole 在 8080）
            r"""bash -lc 'pgrep -f org.apache.catalina.startup.Bootstrap >/dev/null \
    || catalina.sh start \
    || (catalina.sh run >/var/log/catalina-run.log 2>&1 &)'""",

            # Clean volume
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

            # Add apps to dock
            r"""bash -lc 'set -eux; rm -f /etc/dconf/db/local.d/00-infant /etc/dconf/db/local.d/00-favorites || true; mkdir -p /etc/dconf/db/local.d /etc/dconf/profile; printf "%s\n" "user-db:user" "system-db:local" > /etc/dconf/profile/user; printf "%s\n" "[org/gnome/shell]" "favorite-apps=['\''google-chrome.desktop'\'','\''code.desktop'\'','\''thunderbird.desktop'\'','\''libreoffice-writer.desktop'\'','\''libreoffice-calc.desktop'\'','\''libreoffice-impress.desktop'\'','\''org.gnome.Terminal.desktop'\'','\''org.gnome.Nautilus.desktop'\'','\''org.gnome.Settings.desktop'\'']" "" "[org/gnome/shell/extensions/dash-to-dock]" "show-mounts=false" "show-trash=false" "dash-max-icon-size=48" > /etc/dconf/db/local.d/00-favorites; dconf update'
"""
            # skip secrate check
            r"""bash -lc 'set -euo pipefail; apt-get update && apt-get install -y gnome-keyring dbus-user-session && install -d -m 755 /etc/xdg/autostart && printf "[Desktop Entry]\nType=Application\nName=Secret Service (gnome-keyring)\nExec=/usr/bin/gnome-keyring-daemon --start --components=secrets\nOnlyShowIn=GNOME;GNOME-Flashback;Unity;XFCE;LXDE;MATE;\nX-GNOME-Autostart-Phase=Initialization\nX-GNOME-Autostart-Notify=false\nNoDisplay=true\n" > /etc/xdg/autostart/gnome-keyring-secrets.desktop'
"""
            # Open desktop
            r"""bash -lc 'dpkg -s xorgxrdp >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends xrdp xorgxrdp guacd)'
""",
            r"""bash -lc 'set -eux; mkdir -p /var/run/xrdp; chown xrdp:xrdp /var/run/xrdp || true; getent group ssl-cert >/dev/null && adduser xrdp ssl-cert || true; pgrep -x xrdp-sesman >/dev/null || (/usr/sbin/xrdp-sesman -n  >/var/log/xrdp-sesman.foreground.log 2>&1 &); pgrep -x xrdp >/dev/null        || (/usr/sbin/xrdp -n       >/var/log/xrdp.foreground.log        2>&1 &); pgrep -x guacd >/dev/null        || (/usr/sbin/guacd -f      >/var/log/guacd.foreground.log       2>&1 &); ss -lntp 2>/dev/null | grep -E ":(3389|4822)\\b" || true'
""",
            r"""bash -lc 'pgrep -f org.apache.catalina.startup.Bootstrap >/dev/null || catalina.sh start || (catalina.sh run >/var/log/catalina-run.log 2>&1 &)'
""",
#             r"""bash -lc 'set -euo pipefail; HN=$(hostname); grep -qE "(^|[[:space:]])${HN}([[:space:]]|$)" /etc/hosts || echo "127.0.1.1 ${HN}" | sudo tee -a /etc/hosts >/dev/null; if id infant >/dev/null 2>&1; then U=$(id -u infant); G=$(id -g infant); XHOME=$(getent passwd infant | cut -d: -f6); else U=$(id -u); G=$(id -g); XHOME=$(getent passwd "$(id -un)" | cut -d: -f6); [ -n "$XHOME" ] || XHOME="${HOME}"; fi; XAUTH="${XHOME}/.Xauthority"; sudo -u \#${U} mkdir -p "${XHOME}"; [ -e "${XAUTH}" ] || sudo -u \#${U} touch "${XAUTH}"; sudo chown ${U}:${G} "$XAUTH" || sudo chown ${U} "$XAUTH"; sudo chmod 600 "$XAUTH"; sudo rm -f "$XAUTH"-c "$XAUTH"-l "$XAUTH".lock || true; COOKIE=$(sudo -u \#${U} XAUTHORITY="$XAUTH" xauth list 2>/dev/null | awk '\''/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}'\''); [ -n "$COOKIE" ] || COOKIE=$(mcookie); HOST=$(hostname); for name in ":10" "$HOST/unix:10" "localhost/unix:10"; do sudo -u \#${U} XAUTHORITY="$XAUTH" xauth add "$name" . "$COOKIE"; done; export DISPLAY=:10 XAUTHORITY="$XAUTH"; C2=$(xauth -f "$XAUTHORITY" list | awk '\''$1 ~ /(^|\/)unix:10$/ && $3=="MIT-MAGIC-COOKIE-1" {print $NF; exit}'\''); [ -n "$C2" ] || C2=$(xauth -f "$XAUTHORITY" list | awk '\''/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}'\''); for name in ":10" "$HOST/unix:10" "localhost/unix:10"; do xauth -f "$XAUTHORITY" add "$name" . "$C2"; done; if command -v xdpyinfo >/dev/null 2>&1; then xdpyinfo >/dev/null && echo "X OK (:10)" || echo "X FAIL"; else echo "xdpyinfo not installed, skipping check"; fi'
# """
        ]

        for cmd in cmds:
            code, logs = self.container.exec_run(['/bin/bash', '-lc', cmd])
            if code != 0:
                raise RuntimeError(f"Guac setup step failed: {cmd}\n{logs.decode(errors='ignore')}")

        # 10) 等待 Web UI 就绪（容器内 8080）
        import time
        start = time.time()
        while time.time() - start < timeout_s:
            code, _ = self.container.exec_run(
                ['/bin/bash', '-lc', 'curl -fsS http://localhost:8080/guacamole/ >/dev/null']
            )
            if code == 0:
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("Guacamole web UI not ready at :8080/guacamole")

    def config_xorg_for_gui(self):
        # 1) 修 /etc/hosts，避免 sudo 的主机名告警
        self.execute("HN=$(hostname)")
        self.execute('grep -qE "(^|\\s)${HN}(\\s|$)" /etc/hosts || echo "127.0.1.1 ${HN}" | sudo tee -a /etc/hosts >/dev/null')
        
        # 2) 变量：目标 Xauthority 路径与 infant 的 UID/GID（若不存在则退回当前用户）
        self.execute("XAUTH=/home/infant/.Xauthority")
        self.execute("U=$(id -u infant 2>/dev/null || id -u)")
        self.execute("G=$(id -g infant 2>/dev/null || id -g)")
        
        # 3) 归还权限并设为 600
        self.execute('sudo chown ${U}:${G} "$XAUTH" || sudo chown ${U} "$XAUTH"')
        self.execute('sudo chmod 600 "$XAUTH"')
        
        # 4) 清理陈旧锁文件
        self.execute('sudo rm -f "$XAUTH"-c "$XAUTH"-l "$XAUTH".lock || true')
        
        # 5) 读取 :10 的 cookie（读不到就生成一枚）
        self.execute("""COOKIE=$(sudo -u \#${U} XAUTHORITY="$XAUTH" xauth list 2>/dev/null | awk '/:10.*MIT-MAGIC-COOKIE-1/ {print $NF; exit}')""")
        self.execute('''[ -n "$COOKIE" ] || COOKIE=$(mcookie)''')
        
        # 6) 写入到常见的三种 key 上（:10 / <hostname>/unix:10 / localhost/unix:10）
        self.execute('HOST=$(hostname)')
        self.execute('sudo -u \#${U} XAUTHORITY="$XAUTH" xauth add ":10" . "$COOKIE"')
        self.execute('sudo -u \#${U} XAUTHORITY="$XAUTH" xauth add "$HOST/unix:10" . "$COOKIE"')
        self.execute('sudo -u \#${U} XAUTHORITY="$XAUTH" xauth add "localhost/unix:10" . "$COOKIE"')
        
        # 7) 导出到当前 shell（让后续命令能直接用）
        self.execute("grep -qx 'export DISPLAY=:10' ~/.bashrc || echo 'export DISPLAY=:10' >> ~/.bashrc && source ~/.bashrc")
        self.execute('export XAUTHORITY=/home/infant/.Xauthority')
        
        # 8) 禁用屏保
        self.execute("gsettings set org.gnome.desktop.session idle-delay 0")
        self.execute("gsettings set org.gnome.desktop.screensaver lock-delay 0")
        self.execute("gsettings set org.gnome.desktop.screensaver lock-enabled false")
        self.execute("gsettings set org.gnome.settings-daemon.plugins.power idle-dim false")
        self.execute("gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 0")
        self.execute("gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'")
        self.execute("gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-timeout 0 || true")
        self.execute("gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' || true")
        self.execute("gsettings set org.gnome.desktop.screensaver idle-activation-enabled false")
        self.execute("gsettings set org.gnome.desktop.lockdown disable-lock-screen true")

        self.execute("source ~/.bashrc")
        
        

    def ensure_and_login_guac(
        self, *,
        base_url: str,           # 例如 "http://localhost:4443/guacamole"
        web_user: str = "web",
        web_pass: str = "web",
        rdp_user: str = "infant",
        rdp_pass: str = "123",
        connection_name: str = "GNOME Desktop (RDP)",
        verify_tls: bool = True,
        timeout: float = 10.0,
    ):
        """一键：容器内自动配置 + 登录取直达 URL。"""
        # 先确保容器内配置与进程就绪（GNOME Shell / Dock / polkit / Guac）
        self.ensure_guac_ready(
            web_user=web_user, web_pass=web_pass,
            rdp_user=rdp_user, rdp_pass=rdp_pass,
            connection_name=connection_name,
        )

        # 登录拿 token，并返回直达该连接的 URL
        import requests
        base = base_url.rstrip('/')
        s = requests.Session()
        s.verify = verify_tls

        r = s.post(
            f"{base}/api/tokens",
            data={"username": web_user, "password": web_pass},
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            timeout=timeout,
        )
        r.raise_for_status()
        j = r.json()
        token = j["authToken"]
        data_source = j.get("dataSource") or (j.get("availableDataSources") or ["default", "file"])[0]

        conn_id = None
        if connection_name:
            r = s.get(f"{base}/api/session/data/{data_source}/connections",
                    params={"token": token}, timeout=timeout)
            r.raise_for_status()
            resp = r.json()
            if isinstance(resp, dict):
                for obj in resp.values():
                    if obj.get("name") == connection_name:
                        conn_id = obj.get("identifier")
                        break
            if not conn_id:
                raise RuntimeError(f"Connection '{connection_name}' not found in data source '{data_source}'.")

        index_url = f"{base}/?token={token}"
        client_url = f"{base}/#/client/{conn_id}?token={token}" if conn_id else None
        return {"token": token, "data_source": data_source, "index_url": index_url, "client_url": client_url}


    def automate_nomachine_login(self, initial_session: bool = False):
        logger.info('Attempting to automatically connect to the virtual desktop.')
        new_apps = "['google-chrome.desktop', 'code.desktop', 'thunderbird.desktop'," \
           "'libreoffice-writer.desktop', 'libreoffice-calc.desktop', " \
           "'libreoffice-impress.desktop']"
        # prepare for the infant user
        self.execute(f"gsettings set org.gnome.shell favorite-apps \"{new_apps}\"")
        self.execute("pip install Pillow")
        self.execute("sudo chmod -R 777 /workspace/")
        self.execute("source ~/.bashrc")
        
        time.sleep(2) # wait for the installation to finish
        logger.info(f"Please check the details at: 'http://localhost:{self.gui_port}/guacamole'")
        logger.info(f"For first-time users, please go to http://localhost:{self.gui_port}/guacamole to set up and skip unnecessary steps.")
        try:
            # time.sleep(5000) # DEBUG: Check the nomachine login
            if initial_session:
                self.execute("sudo pkill Xvfb")
                self.execute("sudo systemctl stop gdm3")
                self.execute("export DISPLAY=:0")
                self.execute("unset LD_PRELOAD")
                self.execute("nohup Xvfb :0 -screen 0 1920x1080x24 &")
                self.execute("nohup gnome-session &")
                # time.sleep(10) # wait for the nomachine to start
                # self.execute("sed -i -e 's/\\(<option key=\\\"Show [^\\\"]* tutorial\\\" value=\\\"\\)true\\(\\\".*\\)/\\1false\\2/g' -e 's/\\(<option key=\\\"HTTP proxy password for any connections\\\" value=\\\"\\)EMPTY_PASSWORD\\(\\\".*\\)/\\1123\\2/' -e 's/\\(<option key=\\\"HTTP proxy username for any connections\\\" value=\\\"\\)\\\"\\(.*\\)/\\1infant\\\"\\2/' /home/infant/.nx/config/player.cfg")
                # time.sleep(100000) # wait for the nomachine to start
                input("When the computer setup is complete, press Enter to continue") # For setting up the first-time user
        except Exception as e:
            print(f"An error occurred: {e}")

    def find_available_tcp_port(self) -> int:
        """Find an available TCP port, return -1 if none available."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', 0))
            port = sock.getsockname()[1]
            return port
        except Exception:
            return -1
        finally:
            sock.close()

    def get_exec_cmd(self, cmd: str) -> list[str]:
        if self.run_as_infant:
            return ['su', 'infant', '-c', cmd]
        else:
            return ['/bin/bash', '-c', cmd]

    def read_logs(self, id) -> str:
        if id not in self.background_commands:
            raise ComputerInvalidBackgroundCommandError()
        bg_cmd = self.background_commands[id]
        return bg_cmd.read_logs()

    def _send_interrupt(
        self,
        cmd: str,
        prev_output: str = '',
        ignore_last_output: bool = False,
    ) -> tuple[int, str]:
        logger.exception(
            f'Command "{cmd}" timed out, killing process...', exc_info=False
        )
        # send a SIGINT to the process
        if 'shell' in cmd: # kill shell env (if any)
            self.ssh.sendline('quit()')
        self.ssh.sendintr()
        self.ssh.prompt()
        command_output = prev_output
        if not ignore_last_output:
            command_output += '\n' + self.ssh.before
        return (
            -1,
            f'Command: "{cmd}" timed out. Sent SIGINT to the process: {command_output}',
        )

    def split_bash_commands(self, commands):
        if 'context.execute_javascript' in commands:
            return [commands]   
        NORMAL = 0
        IN_SINGLE_QUOTE = 1
        IN_DOUBLE_QUOTE = 2
        IN_HEREDOC = 3

        state = NORMAL
        heredoc_trigger = None
        result = []
        current_command = []

        i = 0
        while i < len(commands):
            char = commands[i]

            if state == NORMAL:
                if char == "'":
                    state = IN_SINGLE_QUOTE
                    current_command.append(char)
                elif char == '"':
                    state = IN_DOUBLE_QUOTE
                    current_command.append(char)
                elif char == '\\':
                    if i + 1 < len(commands) and commands[i + 1] == '\n':
                        current_command.append(char)
                        i += 1  
                        current_command.append('\n')
                        i += 1
                        continue
                    else:
                        current_command.append(char)
                elif char == '\n':
                    if current_command:
                        result.append(''.join(current_command).strip())
                        current_command = []
                elif char == '<' and commands[i : i + 2] == '<<':
                    state = IN_HEREDOC
                    start_op = i
                    i += 2 
                    while i < len(commands) and commands[i] == ' ':
                        i += 1
                    start = i
                    while i < len(commands) and commands[i] not in [' ', '\n']:
                        i += 1
                    heredoc_raw = commands[start:i]
                    if heredoc_raw and heredoc_raw[0] in ("'", '"') and heredoc_raw[-1] == heredoc_raw[0]:
                        heredoc_trigger = heredoc_raw[1:-1]
                    else:
                        heredoc_trigger = heredoc_raw
                    current_command.append(commands[start_op:i])
                    continue
                else:
                    current_command.append(char)

            elif state == IN_SINGLE_QUOTE:
                current_command.append(char)
                if char == "'" and commands[i - 1] != '\\':
                    state = NORMAL

            elif state == IN_DOUBLE_QUOTE:
                current_command.append(char)
                if char == '"' and commands[i - 1] != '\\':
                    state = NORMAL

            elif state == IN_HEREDOC:
                current_command.append(char)
                if char == '\n' and heredoc_trigger:
                    next_line_start = i + 1
                    j = next_line_start
                    while j < len(commands) and commands[j] != '\n':
                        j += 1
                    next_line = commands[next_line_start:j]
                    if next_line.strip() == heredoc_trigger:
                        current_command.append(next_line)
                        if j < len(commands) and commands[j] == '\n':
                            current_command.append('\n')
                            i = j
                        else:
                            i = j
                        state = NORMAL
                        heredoc_trigger = None
                        continue

            i += 1

        if current_command:
            result.append(''.join(current_command).strip())
        result = [cmd for cmd in result if cmd]
        return result

    def execute(
        self, cmd: str, stream: bool = False, timeout: int | None = None
    ) -> tuple[int, str]:
        timeout = timeout or self.timeout
        # if '<<' in cmd:
        #     commands = [cmd]
        # else:
        commands = self.split_bash_commands(cmd)
        if len(commands) > 1:
            all_output = ''
            for command in commands:
                exit_code, output = self.execute(command)
                if all_output:
                    all_output += '\r\n'
                all_output += str(output)
                if exit_code != 0:
                    return exit_code, all_output
            return 0, all_output

        self.ssh.sendline(cmd)
        # --- 检查是否掉进交互环境，若是则 10 s 后自动退出 ---
        try:
            # 0,1,2 = REPL/pdb   3,4,5 = 分页器   6 = EOF
            idx = self.ssh.expect([
                    r'>>> $',                 # 0  Python REPL
                    r'\(Pdb\)\s*',            # 1  pdb / ipdb
                    r'In \[\d+\]:\s*',        # 2  IPython
                    r'--More--',              # 3  less/more 翻页提示
                    pexpect.EOF               # 6  子进程正常结束
                ],
                timeout=1
            )

            # ---------- 根据 idx 采取动作 -------------------
            if idx in (0, 1, 2):                 # 掉进 Python / pdb / IPython
                time.sleep(10)                   # 留 10 秒调试
                self.ssh.sendline('q')           # pdb 退出
                self.ssh.sendline('quit()')      # Python REPL 退出
                self.ssh.sendintr()              # 兜底 Ctrl-C
            elif idx in (3, 4):               # 正在分页器
                self.ssh.send('q') 
        except Exception:
            pass
        success = self.ssh.prompt(timeout=timeout)
        if not success:
            return self._send_interrupt(cmd)
        command_output = self.ssh.before

        # once out, make sure that we have *every* output, we while loop until we get an empty output
        while True:
            logger.debug('WAITING FOR .prompt()')
            self.ssh.sendline('\n')
            timeout_not_reached = self.ssh.prompt(timeout=1)
            if not timeout_not_reached:
                logger.debug('TIMEOUT REACHED')
                break
            logger.debug('WAITING FOR .before')
            output = self.ssh.before
            logger.debug(
                f'WAITING FOR END OF command output ({bool(output)}): {output}'
            )
            if isinstance(output, str) and output.strip() == '':
                break
            command_output += output
        command_output = command_output.removesuffix('\r\n')

        # get the exit code
        self.ssh.sendline('echo $?')
        self.ssh.prompt()
        exit_code_str = self.ssh.before.strip()
        _start_time = time.time()
        while not exit_code_str:
            self.ssh.prompt(timeout=1)
            exit_code_str = self.ssh.before.strip()
            logger.debug(f'WAITING FOR exit code: {exit_code_str}')
            if time.time() - _start_time > timeout:
                return self._send_interrupt(
                    cmd, command_output, ignore_last_output=True
                )
        cleaned_exit_code_str = exit_code_str.replace('echo $?', '').strip()

        try:
            exit_code = int(cleaned_exit_code_str)
        except ValueError:
            logger.error(f'Invalid exit code: {cleaned_exit_code_str}')
            # Handle the invalid exit code appropriately (e.g., raise an exception or set a default value)
            exit_code = -1  # or some other appropriate default value
            
        return exit_code, command_output

    def copy_to(self, host_src: str, computer_dest: str, recursive: bool = False):
        # mkdir -p computer_dest if it doesn't exist
        exit_code, logs = self.container.exec_run(
            ['/bin/bash', '-c', f'mkdir -p {computer_dest}'],
            workdir=self.computer_workspace_dir,
            environment=self._env,
        )
        if exit_code != 0:
            raise Exception(
                f'Failed to create directory {computer_dest} in computer: {logs}'
            )

        # use temp directory to store the tar file to avoid
        # conflict of filename when running multi-processes
        with tempfile.TemporaryDirectory() as tmp_dir:
            if recursive:
                assert os.path.isdir(
                    host_src
                ), 'Source must be a directory when recursive is True'
                files = glob(host_src + '/**/*', recursive=True)
                srcname = os.path.basename(host_src)
                tar_filename = os.path.join(tmp_dir, srcname + '.tar')
                with tarfile.open(tar_filename, mode='w') as tar:
                    for file in files:
                        tar.add(
                            file,
                            arcname=os.path.relpath(file, os.path.dirname(host_src)),
                        )
            else:
                assert os.path.isfile(
                    host_src
                ), 'Source must be a file when recursive is False'
                srcname = os.path.basename(host_src)
                tar_filename = os.path.join(tmp_dir, srcname + '.tar')
                with tarfile.open(tar_filename, mode='w') as tar:
                    tar.add(host_src, arcname=srcname)

            with open(tar_filename, 'rb') as f:
                data = f.read()
            self.container.put_archive(os.path.dirname(computer_dest), data)

    def get_pid(self, cmd):
        exec_result = self.container.exec_run('ps aux', environment=self._env)
        processes = exec_result.output.decode('utf-8').splitlines()
        cmd = ' '.join(self.get_exec_cmd(cmd))

        for process in processes:
            if cmd in process:
                pid = process.split()[1]  # second column is the pid
                return pid
        return None

    def start_docker_container(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            logger.info('Container status: %s', container.status)
            if container.status != 'running':
                container.start()
                logger.info('Container started')
            elapsed = 0
            while container.status != 'running':
                time.sleep(1)
                elapsed += 1
                if elapsed > self.timeout:
                    break
                container = self.docker_client.containers.get(self.container_name)
        except Exception:
            logger.exception('Failed to start container')

    def remove_docker_container(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            container.stop()
            logger.info('Container stopped')
            container.remove()
            logger.info('Container removed')
            elapsed = 0
            while container.status != 'exited':
                time.sleep(1)
                elapsed += 1
                if elapsed > self.timeout:
                    break
                container = self.docker_client.containers.get(self.container_name)
        except docker.errors.NotFound:
            pass

    def get_working_directory(self):
        exit_code, result = self.execute('pwd')
        if exit_code != 0:
            raise Exception('Failed to get working directory')
        return str(result).strip()

    def _source_bashrc(self):
        if self.run_as_infant:
            exit_code, output = self.execute('source /infant/bash.bashrc && source ~/.bashrc')
            if exit_code != 0:
                raise RuntimeError(
                    f'Failed to source /infant/bash.bashrc and ~/.bashrc with exit code {exit_code} and output: {output}'
                )
            logger.info('Sourced /infant/bash.bashrc and ~/.bashrc successfully')
        else:
            exit_code, output = self.execute('source ~/.bashrc')
            if exit_code != 0:
                raise RuntimeError(
                    f'Failed to source ~/.bashrc with exit code {exit_code} and output: {output}'
                )
            logger.info('Sourced ~/.bashrc successfully')
            
    def is_container_running(self):
        try:
            container = self.docker_client.containers.get(self.container_name)
            if container.status == 'running':
                self.container = container
                return True
            return False
        except docker.errors.NotFound:
            return False

    def restart_docker_container(self):
        
        # remove the container if it exists
        try:
            self.remove_docker_container()
        except docker.errors.DockerException as ex:
            logger.exception('Failed to remove container', exc_info=False)
            raise ex

        # start the container
        try:
            network_kwargs: dict[str, str | dict[str, int]] = {}
            if self.use_host_network:
                network_kwargs['network_mode'] = 'host'
            else:
                network_kwargs['ports'] = {f'{self._ssh_port}/tcp': self._ssh_port}
                logger.warning('Using port forwarding till the enable host network mode of Docker is out of experimental mode.')
            logger.info(f'Mounting volumes: {self.volumes}')
            if self.text_only_docker:
                self.container = self.docker_client.containers.run(
                    self.container_image,
                    # allow root login
                    command=f"/usr/sbin/sshd -D -p {self._ssh_port} -o 'PermitRootLogin=yes'",
                    **network_kwargs,
                    working_dir=self.computer_workspace_dir,
                    name=self.container_name,
                    detach=True,
                    volumes=self.volumes,
                )
            else:
                volumes_option = " ".join([f"-v {host}:{bind['bind']}:{bind['mode']}" for host, bind in self.volumes.items()])
                command = (
                    f"docker run --detach --privileged --userns=host --ipc=host "
                    f"--shm-size=2g --cap-add=SYS_ADMIN --cap-add=SYS_BOOT "
                    f"--device=/dev/tty0 "
                    f"-p 4000:{self.nomachine_bind_port} "
                    # f"-p 22:{self.ssh_bind_port} "
                    f"-p 4443:{self.gui_port} "
                    f"-p {self._ssh_port}:{self._ssh_port} "
                    f"{volumes_option} "
                    f"--env CreateUserAccount=infant --env RenderType={self.render_type} "
                    f"--env NvidiaDriver={self.nvidia_driver} "
                    f"--env NVIDIA_VISIBLE_DEVICES={self.nvidia_visible_devices} "
                    f"--env DISPLAY=:0 "
                    f"{self.container_image} /sbin/init -D -o 'PermitRootLogin=yes'"
                )
                logger.info(f"Docker Command:\n{command}")
                self.container = self.docker_client.containers.run(
                    image=self.container_image,
                    name=self.container_name,
                    detach=True,
                    privileged=True,
                    userns_mode='host',
                    ipc_mode='host',
                    shm_size='2g',
                    cap_add=['SYS_ADMIN', 'SYS_BOOT'],
                    devices=['/dev/tty0'],
                    # ports={
                    #     4000: self.nomachine_bind_port,
                    #     # 22: self.ssh_bind_port,
                    #     22: self._ssh_port,
                    #     4443: self.gui_port,
                    #     # f'{self._ssh_port}/tcp':self._ssh_port,
                    # },
                    ports={
                        '8080/tcp': self.gui_port,   # 容器 8080 -> 宿主 4443（例如 self.gui_port=4443）
                        '22/tcp': self._ssh_port,    # 容器 22   -> 宿主 SSH 端口（例如 58673）
                        '3389/tcp': 3389,            # 可选：XRDP（容器3389 -> 宿主3389）
                    },
                    volumes=self.volumes,
                    environment={
                        'CreateUserAccount': "infant" if self.run_as_infant else "root",
                        'RenderType': self.render_type,
                        'NvidiaDriver': self.nvidia_driver,
                        'NVIDIA_VISIBLE_DEVICES': self.nvidia_visible_devices,
                        'DISPLAY': ':0'
                    },
                    command="/sbin/init -D -o 'PermitRootLogin=yes'",
                )
            logger.info('Container started')
            container_status = self.container.status
            # self.container.exec_run
            logger.info(f'Container status: {container_status}')
        except Exception as ex:
            logger.exception('Failed to start container: ' + str(ex), exc_info=False)
            raise ex

        # wait for container to be ready
        elapsed = 0
        while self.container.status != 'running':
            if self.container.status == 'exited':
                logger.info('container exited')
                logger.info('container logs:')
                logger.info(self.container.logs())
                break
            time.sleep(1)
            elapsed += 1
            self.container = self.docker_client.containers.get(self.container_name)
            logger.info(f'waiting for container to start: {elapsed}, container status: {self.container.status}')
            if elapsed > self.timeout:
                break
        if self.container.status != 'running':
            raise Exception('Failed to start container')

    def set_volumes(self):
        mount_dir = self.workspace_mount_path
        logger.info(f'Mounting workspace directory: {mount_dir}')
        return {
            # '/sys/fs/cgroup': {'bind': '/sys/fs/cgroup', 'mode': 'rw'},
            mount_dir: {'bind': self.computer_workspace_dir, 'mode': 'rw'},
            self.cache_dir: {'bind': ('/home/infant/.cache' if self.run_as_infant else '/root/.cache'),'mode': 'rw',},
        }

    # clean up the container, cannot do it in __del__ because the python interpreter is already shutting down
    def close(self):
        containers = self.docker_client.containers.list(all=True)
        for container in containers:
            try:
                if container.name.startswith(self.container_name):
                    if self.consistant_computer:
                        continue
                    container.remove(force=True)
            except docker.errors.NotFound:
                pass
        self.docker_client.close()

    # Run command in the computer
    # def split_commands_by_and(self, commands):
    #     split_commands = []
    #     commands = self.split_bash_commands(commands)
    #     for command in commands:
    #         if 'context.execute_javascript' in command:
    #             split_commands.append(command)
    #             continue
    #         split_commands += command.split('&&')
        
    #     return [cmd.strip() for cmd in split_commands]
    
    def _run_immediately(self, command: str) -> str:
        try:
            command_trace_outputs = ''
            command_outputs =''
            commands = self.split_bash_commands(command)
            for command in commands: 
                trace_output = None 
                if self.trace and ('python ' in command or 'python3' in command): 
                    py_file = None
                    parts = command.split()
                    for part in parts:
                        if part.endswith('.py'):
                            py_file = part
                            break
                        
                    # put the python command into a wrapper
                    if py_file: 
                        mv_switch = True
                        save_original_file_flag = False
                        print(f'Will add trace code in {py_file}')
                        # execute the original code first
                        exit_code, output = self.execute(command)
                        
                        # The trace for debugging
                        trace_code = tool_trace_code

                        # filter bash code
                        filter_bash_code = tool_filter_bash_code

                        # Save the original file to the temp.py
                        save_original_file_content = f"cat {py_file} > /tmp/temp.py"
                        debug_exit_code, debug_output = self.execute(save_original_file_content)   
                        if debug_exit_code != 0:
                            mv_switch = False  # If this step fail, stop tracing
                        else:
                            save_original_file_flag = True # If this step pass, make sure to restore the file           
                        
                        # Add the trace_code to the tmp .py file
                        if mv_switch == True:
                            debug_exit_code, debug_output = self.execute(f"cat << 'EOF' > /tmp/trace_code.py\n{trace_code}\nEOF") 
                            if debug_exit_code != 0:
                                mv_switch = False                               
                            debug_exit_code, debug_output = self.execute(f'cat {py_file} >> /tmp/trace_code.py') 
                            if debug_exit_code != 0:
                                mv_switch = False                               
                            
                        # Move tmp .py file to original .py file
                        if mv_switch == True:
                            debug_exit_code, debug_output = self.execute(f'mv /tmp/trace_code.py {py_file}')   
                            # print(f'debug_exit_code:{debug_exit_code}\ndebug_output:{debug_output}') 
                            if debug_exit_code != 0:
                                mv_switch = False                               
                        
                        # Add the filter_bash_code to the computer
                        if mv_switch == True:
                            add_filter_bash_command = f"cat << 'EOF' > /tmp/temp.sh\n{filter_bash_code}\nEOF"
                            self.execute(add_filter_bash_command)
                            if debug_exit_code != 0:
                                mv_switch = False                               
                        
                        # Run the Trace code and send to temp.txt
                        if mv_switch == True:
                            if command.strip().endswith('&'):
                                command = f"{command.strip().rstrip('&').strip()} > /tmp/temp.txt &"
                            else:
                                debug_exit_code, debug_output = self.execute(f'{command} > /tmp/temp.txt')                         
                                                
                        # Run the filter_bash_code to extract the final_output.txt
                        if mv_switch == True:
                            debug_exit_code, debug_output = self.execute('bash /tmp/temp.sh')
                            if debug_exit_code != 0:
                                mv_switch = False
                        
                        # Get the output
                        if mv_switch == True:
                            trace_exit_code, trace_output = self.execute('cat /tmp/final_output.txt')
                        
                        # Clean the trace code
                        if save_original_file_flag == True: # ensure the trace code got cleaned
                            clean_trace_command = f"cat /tmp/temp.py > {py_file}"
                            debug_exit_code, debug_output = self.execute(clean_trace_command)
                    else:
                        exit_code, output = self.execute(command)   
                else:
                    exit_code, output = self.execute(command)
                
                if 'pip install' in command and 'Successfully installed' in output:
                    print(output)
                    output = 'Package installed successfully'
                output = re.sub(r'\x1b\[[0-9;]*[mK]', '', output)
                command_outputs += f'{output}\n'
                
                # clean the command itself
                if command_outputs.startswith(command):
                    command_outputs = command_outputs[len(command):].strip()
                    
                if trace_output is not None:
                    trace_output = re.sub(r'\x1b\[[0-9;]*[mK]', '', trace_output)
                    command_trace_outputs += f'{trace_output}\n'
                    
            command_outputs = command_outputs.strip()    
            command_trace_outputs = command_trace_outputs.strip()
            
            if command_trace_outputs != '':
                return f'(exit code={exit_code})\n{str(command_outputs)}\nTraced function:\n{str(command_trace_outputs)}'
            else:
                return f'(exit code={exit_code})\n{str(command_outputs)}'                
        except UnicodeDecodeError:
            return 'Command output could not be decoded as utf-8'
        
    def _run_command(self, command: str) -> str:
        return self._run_immediately(command)
    
    async def run_command(self, memory: CmdRun) -> str:
        command = memory.command
        return self._run_immediately(command)
    
    async def run_ipython(self, memory: IPythonRun) -> str:
        
        # run these commands locally
        for func_name in ['parse_audio', 'parse_video', 'watch_video']:
            local_vars = {}
            if func_name in memory.code:
                code = memory.code.replace(func_name, f'result = {func_name}')
                exec(code, globals(), local_vars)
                return str(local_vars['result'])       
        
        # The real output from the code.
        obs = self._run_command(
            ("cat > /tmp/infant_jupyter_temp.py <<'EOL'\n" f'{memory.code}\n' 'EOL'),
        )
        # run the code
        obs = self._run_command(
            ('cat /tmp/infant_jupyter_temp.py | execute_cli.sh'), 
        )
        output = obs
        
        if 'pip install' in memory.code and 'Successfully installed' in output:
            print(output)
            restart_kernel = 'import IPython\nIPython.Application.instance().kernel.do_shutdown(True)'
            if (
                'Note: you may need to restart the kernel to use updated packages.'
                in output
            ):
                obs = self._run_command(
                    (
                        "cat > /tmp/infant_jupyter_temp.py <<'EOL'\n"
                        f'{restart_kernel}\n'
                        'EOL'
                    ),
                )
                obs = self._run_command(
                    ('cat /tmp/infant_jupyter_temp.py | execute_cli'),
                )
                output = '[Package installed successfully]'
                if "{'status': 'ok', 'restart': True}" != obs.strip():
                    print(obs)
                    output += '\n[But failed to restart the kernel to load the package]'
                else:
                    output += '\n[Kernel restarted successfully to load the package]'

                # re-init the kernel after restart
                if memory.kernel_init_code:
                    obs = self._run_command(
                        (
                            f"cat > /tmp/infant_jupyter_init.py <<'EOL'\n"
                            f'{memory.kernel_init_code}\n'
                            'EOL'
                        ),
                    )
                    obs = self._run_command(
                        'cat /tmp/infant_jupyter_init.py | execute_cli',
                    )
        if '<|Basic check failed|>' in output:
            memory.basic_check = False # FIXME: Do we still need this, if we have a critic model?
            return f'{output}'
        return f'{output}'

    def run_python(self, code: str) -> str:
        
        # The real output from the code.
        obs = self._run_command(
            ("cat > /tmp/infant_jupyter_temp.py <<'EOL'\n" f'{code}\n' 'EOL'),
        )
        # run the code
        obs = self._run_command(
            ('cat /tmp/infant_jupyter_temp.py | execute_cli.sh'), 
        )
        output = obs
        
        return f'{output}'

    def get_file(self, file_path: str) -> Optional[bytes]:
        """
        Gets a file from the server.
        """
        logger.info(f"Getting file: {file_path} from the server.")
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        for _ in range(5):
            try:
                response = requests.post(http_server + "/file", data={"file_path": file_path})
                if response.status_code == 200:
                    logger.info("File downloaded successfully")
                    return response.content
                else:
                    logger.error("Failed to get file. Status code: %d", response.status_code)
                    logger.info("Retrying to get file.")
            except Exception as e:
                logger.error("An error occurred while trying to get the file: %s", e)
                logger.info("Retrying to get file.")
            time.sleep(3)

        logger.error("Failed to get file.")
        return None
    
    def get_vm_desktop_path(self) -> Optional[str]:
        """
        Gets the desktop path of the vm.
        """
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        for _ in range(5):
            try:
                response = requests.post(http_server + "/desktop_path")
                if response.status_code == 200:
                    logger.info("Got desktop path successfully")
                    return response.json()["desktop_path"]
                else:
                    logger.error("Failed to get desktop path. Status code: %d", response.status_code)
                    logger.info("Retrying to get desktop path.")
            except Exception as e:
                logger.error("An error occurred while trying to get the desktop path: %s", e)
                logger.info("Retrying to get desktop path.")
            time.sleep(3)

        logger.error("Failed to get desktop path.")
        return None

    def get_vm_directory_tree(self, path) -> Optional[Dict[str, Any]]:
        """
        Gets the directory tree of the vm.
        """
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        payload = json.dumps({"path": path})

        for _ in range(5):
            try:
                response = requests.post(http_server + "/list_directory", headers={'Content-Type': 'application/json'}, data=payload)
                if response.status_code == 200:
                    logger.info("Got directory tree successfully")
                    return response.json()["directory_tree"]
                else:
                    logger.error("Failed to get directory tree. Status code: %d", response.status_code)
                    logger.info("Retrying to get directory tree.")
            except Exception as e:
                logger.error("An error occurred while trying to get directory tree: %s", e)
                logger.info("Retrying to get directory tree.")
            time.sleep(3)

        logger.error("Failed to get directory tree.")
        return None

    def get_accessibility_tree(self) -> Optional[str]:
        """
        Gets the accessibility tree from the server. None -> no accessibility tree or unexpected error.
        """
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        
        for _ in range(5):
            try:
                response: requests.Response = requests.get(http_server + "/accessibility")
                if response.status_code == 200:
                    logger.info("Got accessibility tree successfully")
                    return response.json()["AT"]
                else:
                    logger.error("Failed to get accessibility tree. Status code: %d", response.status_code)
                    logger.info("Retrying to get accessibility tree.")
            except Exception as e:
                logger.error("An error occurred while trying to get the accessibility tree: %s", e)
                logger.info("Retrying to get accessibility tree.")
            time.sleep(3)

        logger.error("Failed to get accessibility tree.")
        return None
    
    def get_vm_wallpaper(self):
        """
        Gets the wallpaper of the vm.
        """
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        for _ in range(5):
            try:
                response = requests.post(http_server + "/wallpaper")
                if response.status_code == 200:
                    logger.info("Got wallpaper successfully")
                    return response.content
                else:
                    logger.error("Failed to get wallpaper. Status code: %d", response.status_code)
                    logger.info("Retrying to get wallpaper.")
            except Exception as e:
                logger.error("An error occurred while trying to get the wallpaper: %s", e)
                logger.info("Retrying to get wallpaper.")
            time.sleep(3)

        logger.error("Failed to get wallpaper.")
        return None

    def get_terminal_output(self) -> Optional[str]:
        """
        Gets the terminal output from the server. None -> no terminal output or unexpected error.
        """
        vm_ip = '172.17.0.2'
        server_port = '5000'
        http_server = f"http://{vm_ip}:{server_port}"
        for _ in range(5):
            try:
                response = requests.get(http_server + "/terminal")
                if response.status_code == 200:
                    logger.info("Got terminal output successfully")
                    return response.json()["output"]
                else:
                    logger.error("Failed to get terminal output. Status code: %d", response.status_code)
                    logger.info("Retrying to get terminal output.")
            except Exception as e:
                logger.error("An error occurred while trying to get the terminal output: %s", e)
                logger.info("Retrying to get terminal output.")
            time.sleep(3)

        logger.error("Failed to get terminal output.")
        return None