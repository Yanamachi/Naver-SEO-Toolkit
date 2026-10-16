"""Presentation-only redaction. Source JSON is never changed."""

import re
import unicodedata

MASK = "[MASKED]"
SENSITIVE = re.compile(
    r"password|passwd|pwd|token|secret|credential|authorization|cookie|session|"
    r"api[-_]?key|access[-_]?key|signature|private[-_]?key", re.I,
)
URL_TEXT = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|//|(?<!\w)/|(?<!\w)\.{1,2}/)[^\s<>\"']+"
    r"|(?<!\w)[\w.-]+\.[a-z0-9]{1,10}[?#][^\s<>\"']+"
)


def _mask_url(match):
    value = match.group()
    value = re.sub(r"\?[^#]*", "?[MASKED]", value)
    return re.sub(r"#.*", "#[MASKED]", value)


def mask_text(value: str) -> str:
    # Query values and fragments may contain arbitrary, unknown secret names.
    value = re.sub(r"(?i)([a-z][a-z0-9+.-]*://|//)[^\s/<>]+@", r"\1[MASKED]@", value)
    value = URL_TEXT.sub(_mask_url, value)
    # A standalone query must contain an immediate key=value, unlike prose '?'.
    value = re.sub(r"\?(?=[^\s<>\"'#?=]+=)[^\s<>\"']*", "?[MASKED]", value)
    value = re.sub(r"(?i)\b(Bearer|Basic)\s+[^\s<>\"']+", r"\1 [MASKED]", value)
    value = re.sub(
        r"(?i)\b([\w-]*(?:password|passwd|pwd|token|secret|credential|authorization|cookie|session|api[_-]?key|access[_-]?key|signature)[\w-]*)\s*[:=]\s*[^\r\n]+",
        r"\1=[MASKED]", value,
    )
    # Suppress terminal escape sequences, bidi controls and other control chars.
    return "".join(c if unicodedata.category(c) not in {"Cc", "Cf", "Cs"} else " " for c in value)


def redact(value):
    if isinstance(value, dict):
        sensitive_source = isinstance(value.get("source"), str) and SENSITIVE.search(value["source"])
        return {
            mask_text(str(key)): MASK if SENSITIVE.search(str(key)) or (key == "value" and sensitive_source)
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return mask_text(value)
    return value
