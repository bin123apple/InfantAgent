import os
import shutil
from infant.util.logger import infant_logger as logger

def backup_image_memory(memory, mount_path, backup_dir="/home/uconn/BinLei/Backup/osworld/images"):
    if '<Screenshot saved at>' in memory.result: # image situation
        lines = memory.result.splitlines()
        # find the last line containing '<Screenshot saved at>'
        last_line = None
        for line in reversed(lines):
            if '<Screenshot saved at>' in line:
                last_line = line
                break
        # extract the path
        if last_line is not None:
            screenshot_path = last_line.split('<Screenshot saved at>')[-1].strip()
        if screenshot_path.startswith("/workspace"):
            image_path = screenshot_path.replace("/workspace", mount_path, 1)

            # Ensure backup directory exists
            os.makedirs(backup_dir, exist_ok=True)

            # Define target path
            target_path = os.path.join(backup_dir, os.path.basename(image_path))

            # Copy the image
            shutil.copy(image_path, target_path)
            logger.info(f"Image backed up to {target_path}")


def backup_image(image_path, mount_path, backup_dir="/home/uconn/BinLei/Backup/osworld/images"):

    # Ensure backup directory exists
    os.makedirs(backup_dir, exist_ok=True)

    # Define target path
    target_path = os.path.join(backup_dir, os.path.basename(image_path))

    # Copy the image
    shutil.copy(image_path, target_path)
    logger.info(f"Image backed up to {target_path}")
