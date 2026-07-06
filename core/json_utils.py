"""
Robust JSON extraction from LLM output.

Local models (llama3, etc.) often wrap JSON in markdown fences, add preamble
text, or produce slightly malformed JSON. This module provides utilities to
extract valid JSON from noisy LLM responses.
"""

from __future__ import annotations
import json
import re
from typing import Any


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def extract_json(text: str) -> Any:
    """
    Attempt to extract and parse JSON from an LLM response.

    Tries multiple strategies in order:
    1. Direct parse after fence-stripping
    2. Find first JSON array [...] in the text
    3. Find first JSON object {...} in the text
    4. Repair common issues (trailing commas, single quotes)
    """
    cleaned = _strip_fences(text)

    # Strategy 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find JSON array
    arr_match = re.search(r"\[[\s\S]*\]", cleaned)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 3: find JSON object
    obj_match = re.search(r"\{[\s\S]*\}", cleaned)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: light repair — trailing commas, single-quoted strings
    repaired = re.sub(r",\s*([}\]])", r"\1", cleaned)      # trailing commas
    repaired = re.sub(r"'([^']*)'", r'"\1"', repaired)     # single → double quotes
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Strategy 5: array inside repaired
    arr2 = re.search(r"\[[\s\S]*\]", repaired)
    if arr2:
        try:
            return json.loads(arr2.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from response:\n{text[:400]}")
