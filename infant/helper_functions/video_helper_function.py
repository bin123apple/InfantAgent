import os
import cv2
import time
import traceback
import subprocess
from typing import Tuple
from urllib.parse import urlparse
import infant.util.constant as constant
from moviepy import VideoFileClip, AudioFileClip
from pathlib import Path

def extract_audio_with_moviepy(video_path: str) -> str:
    """
    Extracts audio from a video and saves it to a file with the same name but a different extension.

    Args:
        video_path (str): Path to the input video file.
        audio_ext (str): Desired audio file extension (e.g., '.mp3', '.m4a', '.wav').

    Returns:
        str: Path to the saved audio file.
    """
    audio_ext: str = ".m4a"
    video = VideoFileClip(video_path)
    audio = video.audio
    if audio is None:
        raise ValueError("No audio track found in video.")

    output_path = str(Path(video_path).with_suffix(audio_ext))
    audio.write_audiofile(output_path)
    return output_path

def download_youtube_video_and_audio(url: str, output_dir: str = ".") -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    
    video_output_path = os.path.join(output_dir, "%(title)s_video.%(ext)s")
    audio_output_path = os.path.join(output_dir, "%(title)s_audio.%(ext)s")

    subprocess.run([
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]",
        "-o", video_output_path,
        url
    ], check=True)

    subprocess.run([
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]",
        "-o", audio_output_path,
        url
    ], check=True)

    video_files = [f for f in os.listdir(output_dir) if f.endswith("_video.mp4")]
    audio_files = [f for f in os.listdir(output_dir) if f.endswith("_audio.m4a")]
    video_files.sort(key=lambda f: os.path.getmtime(os.path.join(output_dir, f)), reverse=True)
    audio_files.sort(key=lambda f: os.path.getmtime(os.path.join(output_dir, f)), reverse=True)

    if not video_files or not audio_files:
        raise FileNotFoundError("Failed to download video or audio.")

    video_path = os.path.join(output_dir, video_files[0])
    audio_path = os.path.join(output_dir, audio_files[0])
    
    # convert to mp3
    base = os.path.splitext(audio_path)[0]
    audio_mp3_path = base + ".mp3"
    audio_clip = AudioFileClip(audio_path)
    audio_clip.write_audiofile(audio_mp3_path)
    return video_path, audio_mp3_path

def watch_video(video_path_or_url: str) -> str:
    """
    Extracts a frame from a video file or URL at the specified time (in seconds).
    Downloads the video if given a URL.

    Args:
        video_path_or_url (str): Local path or YouTube URL.

    Returns:
        str: Path to the saved frame image.
    """
    output = ''
    try:
        video_dir = "/workspace/videos"
        video_dir_local = video_dir.replace("/workspace", constant.MOUNT_PATH, 1)
        os.makedirs(video_dir_local, exist_ok=True)
        
        if urlparse(video_path_or_url).scheme in ("http", "https"):
            video_path_local, audio_path_local = download_youtube_video_and_audio(video_path_or_url, output_dir=video_dir_local)
            video_path = video_path_local.replace(constant.MOUNT_PATH, "/workspace", 1)
            audio_path = audio_path_local.replace(constant.MOUNT_PATH, "/workspace", 1)
            output += f"Downloaded video to: {video_path}\n"
        else:
            video_path = video_path_or_url
            video_path_local = video_path.replace("/workspace", constant.MOUNT_PATH, 1)
            audio_path_local = extract_audio_with_moviepy(video_path_local) 
            audio_path = audio_path_local.replace(constant.MOUNT_PATH, "/workspace", 1)
        output += f"please use the following command:\n"
        output += f"parse_video(video_path='{video_path}', time_sec: float)\n"
        output += f"to watch the video at `time_sec` seconds.\n"
        output += f'I will extract a screenshot from the video at the specified time and provide that to you.\n'
        output += f'If you still want to get more information from the audio of the video, '
        output += f"you can ask me to answer questions based on the video's audio file by using this command:\n"
        output += f"parse_audio(audio_path='{audio_path}', question: str)"
        output += f'I will answer your question based on the audio content.'
    except Exception as e:
        output += "\n<Error occurred>\n"
        output += traceback.format_exc()

    return output

def parse_video(video_path: str, time_sec: float) -> str:   
    output = ''
    try:
        video_path = video_path.replace("/workspace", constant.MOUNT_PATH, 1)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_index = int(fps * time_sec)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

        ret, frame = cap.read()
        if not ret:
            raise ValueError(f"Failed to read frame at {time_sec} seconds (frame {frame_index})")
        
        screenshot_dir = "/workspace/screenshots"
        timestamp = int(time.time())
        screenshot_path = f"{screenshot_dir}/{timestamp}.png"
        output += f"<Screenshot saved at> {screenshot_path}"
        screenshot_path_local = screenshot_path.replace("/workspace", constant.MOUNT_PATH, 1)   
        cv2.imwrite( screenshot_path_local, frame)
        cap.release()
    except Exception as e:
        output += "\n<Error occurred>\n"
        output += traceback.format_exc()

    return output