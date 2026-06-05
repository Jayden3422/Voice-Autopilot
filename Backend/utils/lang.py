def normalize_lang(lang: str | None, default: str = "en") -> str:
    """Normalize locale string to 'en' or 'zh'."""
    if not lang:
        return default
    return "en" if lang.lower().startswith("en") else "zh"
