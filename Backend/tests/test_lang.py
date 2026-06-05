"""Tests for utils/lang.py — language normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.lang import normalize_lang


def test_normalize_en():
    assert normalize_lang("en") == "en"


def test_normalize_en_US():
    assert normalize_lang("en-US") == "en"


def test_normalize_en_GB():
    assert normalize_lang("en-GB") == "en"


def test_normalize_zh():
    assert normalize_lang("zh") == "zh"


def test_normalize_zh_CN():
    assert normalize_lang("zh-CN") == "zh"


def test_normalize_none_returns_default():
    assert normalize_lang(None) == "en"


def test_normalize_empty_returns_default():
    assert normalize_lang("") == "en"


def test_normalize_custom_default():
    """Callers can override the fallback language."""
    assert normalize_lang(None, default="zh") == "zh"
