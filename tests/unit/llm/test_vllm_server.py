# tests/test_oss_llm_integration.py
import os
import pytest
from typing import List
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from infant.llm.llm_oss_base import LLM_OSS_BASED 

# ---- Set vllm server command ----
'''
python -m vllm.entrypoints.openai.api_server \
  --model ByteDance-Seed/UI-TARS-1.5-7B \
  --host 0.0.0.0 --port 8000 \
  --trust-remote-code \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.9
'''

# ---- env vars from system ----
BASE_URL = os.getenv("VLLM_BASE_URL")
MODEL_ID = os.getenv("VLLM_MODEL")
API_KEY = os.getenv("VLLM_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not (BASE_URL and MODEL_ID),
    reason="needs VLLM_BASE_URL and VLLM_MODEL env vars to run"
)

# ---- args fixture ----
class _Args:
    def __init__(self):
        # remote vLLM server
        self.model_oss = MODEL_ID
        self.base_url_oss = BASE_URL
        self.api_key_oss = API_KEY

        # Sampling
        self.sampling_n = 2
        self.max_tokens = 64
        self.vllm_temperature = 0.2
        self.vllm_top_p = 0.95
        self.stop = ["<|exit|>"]

        # local model settings (not used for remote vLLM)
        self.tensor_parallel_size = 1
        self.gpu_memory_utilization = 0.9
        self.max_model_len = 8192
        self.enable_prefix_caching = False
        self.trust_remote_code = True

@pytest.fixture(scope="module")
def args() -> _Args:
    return _Args()

@pytest.fixture(scope="module")
def messages() -> List[dict]:
    return [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Say hello twice, each on its own line."},
    ]

def test_completion_returns_text_list(args, messages):
    """verify: completion and returns list of strings."""
    llm = LLM_OSS_BASED(args)

    out = llm.completion(messages)
    assert isinstance(out, list), "completion Should return list[str]"
    assert len(out) == args.sampling_n, f"Should return {args.sampling_n} samples, got {len(out)}"
    for i, t in enumerate(out):
        assert isinstance(t, str), f"{i} should be str, got {type(t)}"
        assert t.strip(), f"{i} should not be empty"

def test_completion_stop_override(args, messages):
    """verify: custom stop words work."""
    llm = LLM_OSS_BASED(args)
    custom_stop = ["<END>"]
    out = llm.completion(messages, stop=custom_stop)
    assert isinstance(out, list)
    assert len(out) == args.sampling_n

@pytest.mark.timeout(60)  # allow up to 60s for this test
def test_concurrent_messages_no_deadlock(args):
    """
    Test sending multiple concurrent requests to vLLM server.
    """
    llm = LLM_OSS_BASED(args)

    sys_msg = {"role": "system", "content": "You are a concise assistant."}
    user_texts = [
        "Say hello twice, each on its own line.",
        "Say your name twice, each on its own line. Your name is Bot.",
        "Count from 1 to 2, each on its own line.",
        "Output the word 'Alpha' twice on separate lines.",
        "Output 'A' then 'B' on two lines.",
    ]

    def _run_one(utext: str):
        msgs = [sys_msg, {"role": "user", "content": utext}]
        out = llm.completion(msgs, stop=["<END>"])
        try:
            return out.choices[0].message.content
        except AttributeError:
            return out[0] if out else ""

    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(_run_one, t) for t in user_texts]
        results = [f.result() for f in as_completed(futs)]

    elapsed = time.time() - start
    assert len(results) == 5
    assert all(isinstance(r, str) and len(r) > 0 for r in results)

    print(f"[concurrency] 5 reqs finished in {elapsed:.2f}s")