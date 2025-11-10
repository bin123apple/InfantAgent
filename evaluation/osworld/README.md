# OSWorld Evaluation 

We use [OSWorld benchmark](https://os-world.github.io/) to test the **pure vision** ability of our agent.

Because their test scripts contain a large number of evaluation functions, we consolidated all tests into a single script (`run_inference.py`) and ran it using their official repository. The testing steps are as follows:

1. Configure the test environment according to the `README` of [OSWorld](https://github.com/xlang-ai/OSWorld) until you can successfully execute the official `run.py` script.  
2. Place our script in the root directory of the OSWorld project, replace `run.py` with `run_inference.py` in the run command, and then execute the command.

## Performance

**Claude-sonnet-4-5**

### Per-Domain Results (50 Steps + Tools)
| Domain               | Runned | Success Rate |
|:----------------------:|:------:|-------------:|
| chrome               |   45   | 53.24%       |
| thunderbird          |   15   | 60.00%       |
| multi_apps           |   93   | 53.60%       |
| gimp                 |   26   | 61.54%       |
| libreoffice_calc     |   47   | 63.83%       |
| libreoffice_writer   |   23   | 60.86%       |
| libreoffice_impress  |   47   | 55.11%       |
| os                   |   24   | 70.83%       |
| vlc                  |   17   | 75.22%       |
| vs_code              |   23   | 73.91%       |

### Category Summaries
| Category      | Success Rate |
|:---------------:|:-------------:|
| Office        | 59.74%       |
| Daily         | 59.41%       |
| Professional  | 67.35%       |

### Overall
| Total Runned | Current Success Rate |
|:------------:|:---------------------:|
|     360      | 59.86%               |
