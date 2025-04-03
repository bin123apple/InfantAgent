import os
import sys
import time
import traceback

import site
sys.path = [path for path in sys.path if "requests" not in path]
standard_lib_path = os.path.dirname(os.__file__)
site_packages_path = site.getsitepackages()[0]
sys.path.insert(0, standard_lib_path)
sys.path.insert(0, site_packages_path)

import requests

# Read the Python code from STDIN
code = sys.stdin.read()


def execute_code(code, print_output=True):
    PORT = os.environ.get('JUPYTER_EXEC_SERVER_PORT')
    POST_URL = f'http://localhost:{PORT}/execute'

    # Set the default kernel ID
    kernel_id = 'default'
    output = ''
    for i in range(3):
        try:
            response = requests.post(
                POST_URL, json={'kernel_id': kernel_id, 'code': code}
            )
            output = response.text
            if '500: Internal Server Error' not in output:
                if print_output:
                    print(output)
                break
        except requests.exceptions.ConnectionError:
            if i == 2:
                traceback.print_exc()
        time.sleep(2)
    else:
        if not output:
            with open('/infant/logs/jupyter_execute_server.log', 'r') as f:
                output = f.read()
        print('Failed to connect to the Jupyter server', output)


if jupyter_pwd := os.environ.get('JUPYTER_PWD'):
    execute_code(
        f'import os\nos.environ["JUPYTER_PWD"] = "{jupyter_pwd}"\nos.environ["DISPLAY"] = "{os.environ.get("DISPLAY")}"\n', 
        print_output=False
    )

execute_code(code)
