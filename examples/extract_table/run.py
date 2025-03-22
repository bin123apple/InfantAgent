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
    files_to_move = ['1984 Shock Compression of Liquid Helium to 56 GPa (560 kbar), Nellis et al., Phys. Rev. Lett.pdf']
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
        "named `1984 Shock Compression of Liquid Helium to 56 GPa (560 kbar), Nellis et al., Phys. Rev. Lett.pdf`. "
        "I would like to extract Table 1 and Table 2 from the PDF and save them as `.dat` files. "
        "For Table 1, please add an extra column on the right to record the initial molar volume of helium. "
        "For Table 2, please split the single-row table into two rows based on the subscripts of the different physical quantities. "
        "Please only include the table in the final .dat file."
    )
    answer = asyncio.run(extract_table(user_request_text))
    print(answer)