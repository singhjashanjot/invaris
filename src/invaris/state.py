"""Atomic, secret-filtered local checkpoints for bounded runs."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

_SECRET_KEY = re.compile(r"(secret|password|token|private.?key|credential|api.?key)", re.I)
_SECRET_VALUE = re.compile(r"(?i)(\b(?:authorization\s*:\s*bearer|bearer)\s+)[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*['\"]?([^\s,'\";]+)")
_PRIVATE_KEY = re.compile(r"(?s)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_SAFE_TOKEN_KEYS = {"max_tokens", "input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens"}


def _is_secret_key(key: str) -> bool:
    return key.lower() not in _SAFE_TOKEN_KEYS and bool(_SECRET_KEY.search(key))


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if not _is_secret_key(str(key))}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        value = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
        value = _SECRET_VALUE.sub(r"\1[REDACTED]", value)
        return _SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise TypeError(f"unsupported checkpoint value: {type(value).__name__}")


def save_checkpoint(path: str | Path, state: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_state = _sanitize(state)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(safe_state, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError("checkpoint root must be an object")
    return _sanitize(result)
