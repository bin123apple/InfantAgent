# OSWorld Evaluation 

We use [OSWorld benchmark](https://os-world.github.io/) to test the **pure vision** ability of our agent.

Because their test scripts contain a large number of evaluation functions, we consolidated all tests into a single script (`run_inference.py`) and ran it using their official repository. The testing steps are as follows:

1. Configure the test environment according to the `README` of [OSWorld](https://github.com/xlang-ai/OSWorld) until you can successfully execute the official `run.py` script.  
2. Place our script in the root directory of the OSWorld project, replace `run.py` with `run_inference.py` in the run command, and then execute the command.

## Performance

| Model            | Visual localization Model            | Agent Version          | dataset        | Accuracy     |
|:------------------:|:------------------:|:---------------------:|:-------------------:|:------------:|
| Claude-3.7-Sonnet   |UI-TARS-1.5-7B| InfantAgent-2025-04-25   | osworld-test-all    | 35.27%        |
| Gemini-2.5-pro |-| - | -       | TODO       |