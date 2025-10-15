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
    kernel_id = 'default'

    max_retries = 5     
    base_delay = 1   
    output = ''

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                POST_URL,
                json={'kernel_id': kernel_id, 'code': code},
                timeout=(5, 30) 
            )
            response.raise_for_status()

            output = response.text
            if '500: Internal Server Error' in output:
                raise requests.exceptions.HTTPError("Server returned 500 in body")

            if print_output:
                print(output)
            break

        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            if attempt == max_retries:
                traceback.print_exc()
            else:
                delay = base_delay * attempt
                print(f"[Attempt {attempt}/{max_retries}] Error: {e!r}. Retrying in {delay}s…")
                time.sleep(delay)

    else:
        if not output:
            try:
                with open('/infant/logs/jupyter_execute_server.log', 'r') as f:
                    output = f.read()
            except FileNotFoundError:
                output = "<no server log available>"
        print('Failed to connect to the Jupyter server:', output)

if jupyter_pwd := os.environ.get('JUPYTER_PWD'):
    execute_code(
        f'import os\nos.environ["JUPYTER_PWD"] = "{jupyter_pwd}"\nos.environ["DISPLAY"] = "{os.environ.get("DISPLAY")}"\n', 
        print_output=False
    )

execute_code(code)
