import os
import base64
import shutil
import asyncio
from infant.main import initialize_agent, run_single_step

async def extract_table(user_request_text: str):
    
    agent, computer = await initialize_agent()
    computer.execute(f'cd /workspace && rm -rf *')
    computer.execute(f'source ~./bashrc')
    
    # move files to workspace
    files_to_move = ['2008 Fluid helium at conditions of giant planetary interiors, Stixrude and Jeanloz, Proc. Natl. Acad. Sci.pdf']
    workspace_dir = os.path.join(os.getcwd(), 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)

    for filename in files_to_move:
        src = os.path.join(os.getcwd(), filename)
        dst = os.path.join(workspace_dir, filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst) 
            print(f"Copied: {filename} -> workspace/")
        else:
            print(f"File not found: {filename}")
    
    # run
    answer = await run_single_step(agent, user_request_text)
    return answer


if __name__ == "__main__":
    user_request_text = (
        "I uploaded a PDF file in /workspace. "
        "named `2008 Fluid helium at conditions of giant planetary interiors, Stixrude and Jeanloz, Proc. Natl. Acad. Sci.pdf`. "
        "Please help me to view Figure 6B and save the all the data points for 10,000 K, 20,000 K and 50,000 K in three `.dat` files. "
        "For each `.dat` file, it should contain two columns: pressure (GPa) and density (g/cm^3). "
        "Please help me to estimate the data value for each data points from the figure 6B. "
        "The value should be as accurate as possible."
    )
    answer = asyncio.run(extract_table(user_request_text))
    print(answer)