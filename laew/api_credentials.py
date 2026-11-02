"""Persist API keys as Windows user environment variables, never project data."""

import os

from laew.cloud_chat import CloudError


def _notify_environment_change() -> None:
    """Tell Explorer to refresh the environment inherited by new applications."""
    import ctypes
    from ctypes import wintypes
    result = ctypes.c_size_t()
    send = ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                     wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    send(0xFFFF, 0x001A, 0, "Environment", 2, 1000, ctypes.byref(result))


def save_api_key(provider: str, value: str) -> None:
    variable = {"openai-api": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
    if not variable or not isinstance(value, str) or not 8 <= len(value.strip()) <= 4096 or any(c.isspace() for c in value.strip()):
        raise CloudError("INVALID_REQUEST", "Choose an API key provider and enter a valid key without whitespace.")
    if os.name != "nt":
        raise CloudError("UNSUPPORTED_PLATFORM", "Persistent key configuration currently requires Windows. Set the backend environment variable instead.")
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, variable, 0, winreg.REG_SZ, value.strip())
    except OSError:
        raise CloudError("CONFIGURATION", "Could not save the user environment variable.") from None
    os.environ[variable] = value.strip()
    try:
        _notify_environment_change()
    except (OSError, AttributeError):
        # Registry persistence and the current backend already succeeded.
        pass
