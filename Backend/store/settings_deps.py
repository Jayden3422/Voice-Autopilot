from store.settings_store import load


def get_settings_store() -> dict:
    """Load current settings from disk. Not cached — returns live values for every request."""
    return load()
