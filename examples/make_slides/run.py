import os
import base64
import shutil
import asyncio
from infant.main import initialize_agent, run_single_step

async def make_slides(user_request_text: str):
    
    agent, computer = await initialize_agent()
    computer.execute(f'cd /workspace && rm -rf *')
    computer.execute(f'source ~./bashrc')
    
    # run
    answer = await run_single_step(agent, user_request_text)
    return answer


if __name__ == "__main__":
    user_request_text = (
        "Please help me search some bioinformatic papers. "
        "And download those papers to /workspace. "
        "Then you should read those PDF file and make PowerPoint for presentation."
    )
    answer = asyncio.run(make_slides(user_request_text))
    print(answer)