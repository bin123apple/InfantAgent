import os
import base64
import traceback
from infant.config import config
from infant.llm.llm_api_base import LLM_API_BASED
import infant.util.constant as constant

def audio_base64_to_url(audio_path: str) -> str:
    '''
    Convert an audio file to a base64-encoded data URL.
    '''
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File not found: {audio_path}")

    # read the audio file and encode it to base64
    with open(audio_path, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode("utf-8")

    # determine the file type
    file_ext = os.path.splitext(audio_path)[1].lower().replace(".", "")
    if file_ext not in ["wav", "mp3", "m4a"]:
        raise ValueError(f"Unsupported audio format: {file_ext}")

    return encoded_string, file_ext

def parse_audio(audio_path: str, question: str) -> str:
    '''
    Answer this question based on the audio file.
    '''
    output = ''
    try:
        litellm_parameter = config.get_litellm_params()
        litellm_parameter.model = 'gpt-4o-audio-preview'  # Specify the model you want to use
        litellm_parameter.api_key = os.getenv("OPENAI_API_KEY")
        llm = LLM_API_BASED(litellm_parameter)
        audio_path = audio_path.replace("/workspace", constant.MOUNT_PATH, 1)
        audio_base64, audio_type = audio_base64_to_url(audio_path)
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_base64, "format": audio_type},
                    },
                ],
            },
        ]
        answer, _ = llm.completion(messages=messages)
        output += answer
    except Exception as e:
        output += "\n<Error occurred>\n"
        output += traceback.format_exc()
    return output