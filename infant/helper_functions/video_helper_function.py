import os
import cv2
import time
import shlex
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
    try:
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
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to download video/audio, please check your URL.")

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
        output += f"Please first use the following command:\n"
        output += f"parse_video(video_path='{video_path}', time_sec: float)\n"
        output += f'to watch the video at different `time_sec` seconds.\n'
        output += f'I will extract a screenshot from the video at the specified time and provide that to you.\n'
        output += f"If you still can not get enough information after viewing several frames, "
        output += f"you can ask me to answer questions based on the video's audio file by using this command:\n"
        output += f"parse_audio(audio_path='{audio_path}', question: str)\n"
        output += f'I will answer your question based on the audio content.'
    except Exception as e:
        output += "\n<Error occurred>\n"
        output += traceback.format_exc()

    return output

def is_av1_encoded(video_path: str) -> bool:
    try:
        result = subprocess.run(
            [
                "/usr/bin/ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=30  # 超时 30 秒
        )
        codec = result.stdout.strip()
        return codec.lower() == "av1"
    except Exception as e:
        return False

def extract_frame_ffmpeg(video_path: str, time_sec: float, output_image: str) -> None:
    """
    利用 ffmpeg 提取 video_path 视频中 time_sec 时间点的一帧，
    输出到 output_image。利用 -ss 快速定位，-vframes 1 表示只输出一帧。
    """
    quoted_input = shlex.quote(video_path)
    quoted_output = shlex.quote(output_image)
    cmd = f"/usr/bin/ffmpeg -y -nostdin -ss {time_sec} -i {quoted_input} -vframes 1 {quoted_output}"
    try:
        subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=60  
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg frame extraction timed out.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg frame extraction failed:\n{e.stderr.decode()}")

def parse_video(video_path: str, time_sec: float) -> str:
    output = ""
    try:
        video_path = video_path.replace("/workspace", constant.MOUNT_PATH, 1)
        screenshot_dir = "/workspace/screenshots"
        timestamp = int(time.time())
        screenshot_path = f"{screenshot_dir}/{timestamp}.png"
        screenshot_path_local = screenshot_path.replace("/workspace", constant.MOUNT_PATH, 1)

        if is_av1_encoded(video_path):
            output += "[Info] Video is AV1 encoded. Extracting frame using ffmpeg directly...\n"
            extract_frame_ffmpeg(video_path, time_sec, screenshot_path_local)
        else:
            output += "[Info] Video is not AV1 encoded. Using cv2 to extract frame...\n"
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise FileNotFoundError(f"Cannot open video file: {video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps == 0:
                raise ValueError(f"Invalid FPS (0) for video: {video_path}")
            frame_index = int(fps * time_sec)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = cap.read()
            if not ret or frame is None:
                raise ValueError(f"Failed to read frame at {time_sec} seconds (frame {frame_index})")
            cv2.imwrite(screenshot_path_local, frame)
            cap.release()

        output += f"<Screenshot saved at> {screenshot_path}\n"
    except Exception:
        output += "\n<Error occurred>\n" + traceback.format_exc()
    return output


