import base64
import logging
import os
from collections.abc import Callable

log = logging.getLogger(__name__)

NAN_BASE_URL = "https://api.nan.builders/v1"
DEFAULT_MODEL = "qwen3.6"
MAX_TOKENS = 200
TEMPERATURE = 0


def create_client():
    from openai import AsyncOpenAI

    api_key = os.environ.get("NAN_API_KEY") or os.environ.get("VISION_API_KEY")
    base_url = os.environ.get("VISION_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or NAN_BASE_URL
    model = os.environ.get("VISION_MODEL") or DEFAULT_MODEL
    return AsyncOpenAI(api_key=api_key, base_url=base_url), model


async def extract_from_image(
    image_bytes: bytes,
    prompt: str,
    *,
    mime_type: str = "image/jpeg",
    response_model: type | None = None,
    parser: Callable | None = None,
    model_override: str | None = None,
) -> tuple[dict | list | str | None, str | None]:
    client, model = create_client()
    model = model_override or model

    if not client.api_key:
        log.warning("NAN_API_KEY not set; cannot call vision API")
        return None, "missing_api_key"

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        }
        resp = await client.chat.completions.create(**kwargs)
    except Exception as e:
        log.warning("vision API call failed: %s", type(e).__name__)
        return None, f"api_call_failed:{type(e).__name__}"

    try:
        raw = resp.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return None, "malformed_response"

    import re
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    import json
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("vision returned non-JSON: %.200s", cleaned)
        return raw, "json_decode_failed"

    if response_model is not None and not isinstance(data, dict):
        return raw, "not_a_dict"

    if parser is not None:
        return parser(data), None

    return data, None


async def extract_from_text(
    text: str,
    prompt: str,
    *,
    response_model: type | None = None,
    parser: Callable | None = None,
    model_override: str | None = None,
) -> tuple[dict | list | str | None, str | None]:
    client, model = create_client()
    model = model_override or model

    if not client.api_key:
        log.warning("NAN_API_KEY not set; cannot call vision API")
        return None, "missing_api_key"

    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        }
        resp = await client.chat.completions.create(**kwargs)
    except Exception as e:
        log.warning("vision API call failed: %s", type(e).__name__)
        return None, f"api_call_failed:{type(e).__name__}"

    try:
        raw = resp.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return None, "malformed_response"

    import re
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    import json
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("vision returned non-JSON: %.200s", cleaned)
        return raw, "json_decode_failed"

    if response_model is not None and not isinstance(data, dict):
        return raw, "not_a_dict"

    if parser is not None:
        return parser(data), None

    return data, None
