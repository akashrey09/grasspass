"""A tiny client for any OpenAI-compatible chat endpoint.

Ollama, llama.cpp's llama-server, LM Studio and vLLM all speak this protocol, so
swapping the model (or the whole runtime) is one environment variable, and
nothing leaves the machine unless you point it somewhere else.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = "gemma3:4b"
    api_key: str = "local"
    timeout: float = 120.0
    temperature: float = 0.8

    @classmethod
    def from_env(cls) -> "LLMConfig":
        d = cls()
        return cls(
            base_url=os.environ.get("GRASSPASS_BASE_URL", d.base_url),
            model=os.environ.get("GRASSPASS_MODEL", d.model),
            api_key=os.environ.get("GRASSPASS_API_KEY", d.api_key),
            timeout=float(os.environ.get("GRASSPASS_TIMEOUT", d.timeout)),
            temperature=float(os.environ.get("GRASSPASS_TEMPERATURE", d.temperature)),
        )


def extract_json(text: str):
    """Pull the first JSON object out of a model reply, tolerating fences and chatter."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("reply contained no JSON object")
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"reply was not valid JSON ({exc.msg})") from exc


def chat_json(cfg: LLMConfig, system: str, user: str):
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": cfg.temperature,
        "max_tokens": 900,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise LLMError(f"model server returned HTTP {exc.code}", retryable=exc.code >= 500) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise LLMError(f"could not reach model server at {cfg.base_url}", retryable=False) from exc
    except json.JSONDecodeError as exc:
        raise LLMError("model server sent a non-JSON response") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("unexpected response shape from model server") from exc
    if not isinstance(content, str):
        raise LLMError("model reply was not text")
    return extract_json(content)
