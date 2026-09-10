"""API-based visual grounding, as a drop-in for `LLM_OSS_BASED`.

The default grounding model is UI-TARS-1.5-7B served by vLLM on :8888, which
needs a GPU and a ~15 GB download. The consumer side does not actually care
which model answers: `_ask_llm_for_coordinate()` sends one image plus a text
request and `extract_coordinates()` just regexes `(x, y)` (or a 4-tuple box)
out of the reply. So any vision model reachable through litellm can stand in.

This class exposes the one method that path uses -- `completion(messages,
stop=None) -> list[str]` -- and forwards to an API model instead.

Trade-off: a dedicated grounding model is trained to emit exact pixel
coordinates and is more precise at it than a general vision model. Use this
when no GPU is free, or when you would rather not run a second server; prefer
UI-TARS when click accuracy matters.
"""

import base64
import math
import io
import re

from litellm import completion as litellm_completion
from PIL import Image

from infant.util.logger import infant_logger as logger

# Anthropic downsamples any image over the limits before the model sees it, and
# the model then answers in *that* frame -- so left implicit, coordinates come
# back scaled (~0.82 on a 1920px-wide screenshot for a 1568px limit, a ~330px
# error). Resizing here instead makes the mapping explicit and reversible.
#
# The limits are per-model (docs: "Computer use tool" -> image size limits):
#   Opus 4.7 and later   2576 px long edge, ~3.75 MP
#   earlier models       1568 px long edge, ~1.15 MP
# A 1920x1080 screenshot is already inside the newer limits, so on those models
# no resizing happens at all and full resolution reaches the model.
LIMITS_NEW = (2576, 3_750_000)
LIMITS_OLD = (1568, 1_150_000)
NEWER_MODELS = ('opus-4-7', 'opus-4-8', 'opus-5', 'sonnet-5', 'fable-5', 'mythos-5')


def _limits_for(model: str) -> tuple[int, int]:
    m = str(model).lower()
    return LIMITS_NEW if any(k in m for k in NEWER_MODELS) else LIMITS_OLD


def _scale_factor(width: int, height: int, limits: tuple[int, int]) -> float:
    """Anthropic's documented formula: fit both the long edge and total pixels."""
    max_edge, max_pixels = limits
    return min(1.0,
               max_edge / max(width, height),
               math.sqrt(max_pixels / (width * height)))

# `_ask_llm_for_coordinate()` asks only for "the ONE point coordinates (x, y)".
# A general vision model needs to be told the frame of reference as well, or it
# tends to answer in normalized or resized coordinates.
GROUNDING_SYSTEM_PROMPT = (
    "You locate UI elements in screenshots. Answer with the coordinates of the "
    "single point at the CENTER of the requested element, in pixels of the "
    "image exactly as supplied, with the origin (0, 0) at the top-left corner "
    "and x increasing to the right, y increasing downward. Reply with nothing "
    "but the coordinates in the form (x, y) -- no prose, no units, no "
    "normalization, no percentages. If the element is not visible, reply "
    "exactly (-1, -1)."
)


class LLM_VG_API:
    """Visual grounding through an API vision model."""

    def __init__(self, args):
        self.args = args
        self.model = (getattr(args, 'vg_api_model', None)
                      or getattr(args, 'model', None)
                      or 'claude-opus-4-8')
        self.api_key = getattr(args, 'api_key', None)
        self.max_tokens = 64          # a coordinate pair, nothing more
        self.accumulated_cost = 0.0
        # Opus 4.7 and later removed the sampling parameters: any temperature
        # other than the 1.0 default is rejected outright, so a "deterministic"
        # 0.0 would fail every call. Send none on those models.
        self.temperature = None if _limits_for(self.model) is LIMITS_NEW else 0.0
        logger.info(f'Visual grounding via API model: {self.model} '
                    f'(temperature={self.temperature})')

    def _rescale(self, messages):
        """Shrink any inline image to fit the model's limits, reporting the scale.

        Returns (messages, scale) where scale maps model coordinates back to
        the original image: original = model_coord / scale.
        """
        limits = _limits_for(self.model)
        scale = 1.0
        out = []
        for msg in messages:
            content = msg.get('content')
            if not isinstance(content, list):
                out.append(msg)
                continue
            new_content = []
            for part in content:
                url = (part.get('image_url') or {}).get('url', '') if isinstance(part, dict) else ''
                if not url.startswith('data:image'):
                    new_content.append(part)
                    continue
                try:
                    raw = base64.b64decode(url.split(',', 1)[1])
                    img = Image.open(io.BytesIO(raw))
                    s = _scale_factor(img.width, img.height, limits)
                    if s < 1.0:
                        scale = s
                        img = img.resize(
                            (round(img.width * scale), round(img.height * scale)),
                            Image.LANCZOS,
                        )
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
                    new_content.append({'type': 'image_url', 'image_url': {'url': url}})
                    new_content.append({
                        'type': 'text',
                        'text': f'The image is exactly {img.width} x {img.height} pixels.',
                    })
                except Exception as e:
                    logger.warning(f'Could not rescale grounding image: {e}')
                    new_content.append(part)
            out.append({**msg, 'content': new_content})
        return out, scale

    @staticmethod
    def _unscale(text: str, scale: float) -> str:
        """Map the first (x, y) in the reply back to original-image pixels."""
        if scale == 1.0:
            return text
        m = re.search(r'\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', text)
        if not m:
            return text
        x, y = int(m.group(1)), int(m.group(2))
        if x < 0 or y < 0:            # the "not visible" sentinel
            return text
        return f'({round(x / scale)}, {round(y / scale)})'

    def completion(self, messages, stop: list | None = None) -> list[str]:
        messages, scale = self._rescale(list(messages))
        payload = [{'role': 'system', 'content': GROUNDING_SYSTEM_PROMPT}] + list(messages)
        kwargs = dict(model=self.model, api_key=self.api_key, messages=payload,
                      max_tokens=self.max_tokens, stop=stop or None)
        if self.temperature is not None:
            kwargs['temperature'] = self.temperature
        try:
            resp = litellm_completion(**kwargs)
        except Exception as e:
            # extract_coordinates() reads result[0]; returning the sentinel keeps
            # the caller on its "element not found" path instead of raising.
            logger.error(f'Visual grounding call failed: {type(e).__name__}: {e}')
            return ['(-1, -1)']

        try:
            cost = getattr(resp, '_hidden_params', {}).get('response_cost') or 0.0
            self.accumulated_cost += cost
        except Exception:
            pass

        texts = [self._unscale(c.message.content or '', scale) for c in resp.choices]
        logger.debug(f'Visual grounding reply (scale={scale:.3f}): '
                     f'{texts[0][:80] if texts else "<empty>"}')
        return texts or ['(-1, -1)']
