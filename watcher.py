# -*- coding: utf-8 -*-
"""
Определение сайта в активном браузере (только Windows).

Программа смотрит, какое окно сейчас активно. Если это браузер —
читает адресную строку через Windows UI Automation и возвращает
домен открытого сайта (например "vk.com").

Ничего не отправляется в интернет. Если что-то недоступно
(не Windows / нет модуля) — функции просто возвращают None,
и программа работает как обычно.

© Evgeniy Mamonov — evgeniymamonov.com
"""

import re
import sys

# Браузеры, у которых умеем читать адресную строку (имя .exe).
# browser.exe — Яндекс.Браузер.
_BROWSER_EXE = {
    "chrome.exe", "msedge.exe", "browser.exe",
    "brave.exe", "opera.exe", "vivaldi.exe", "firefox.exe",
}

# Возможные имена элемента «адресная строка» в разных браузерах/языках.
_ADDR_NAMES = (
    "Адресная строка и строка поиска",
    "Строка адреса и поиска",
    "Address and search bar",
    "Address bar",
    "Поиск или ввод адреса",
    "Search or enter address",
)

# Что-то похожее на домен (host) в тексте адресной строки.
_HOST_RE = re.compile(
    r"(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9\-]+)+)",
    re.IGNORECASE)


def available():
    """Доступна ли функция слежения на этой системе."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import uiautomation  # noqa: F401
        return True
    except Exception:
        return False


def _active_browser_hwnd():
    """Вернуть hwnd активного окна, если это браузер, иначе None."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        if not ok:
            return None
        exe = buf.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(handle)

    return hwnd if exe in _BROWSER_EXE else None


def _read_address_text(hwnd):
    """Прочитать текст адресной строки браузера через UI Automation."""
    import uiautomation as auto

    win = auto.ControlFromHandle(hwnd)
    if not win:
        return None

    # 1) ищем по известным именам адресной строки
    for name in _ADDR_NAMES:
        try:
            edit = win.EditControl(searchDepth=16, Name=name)
            if edit.Exists(0, 0):
                val = _value_of(edit)
                if val:
                    return val
        except Exception:
            pass

    # 2) запасной путь: первое поле ввода в окне (у Chromium это адресная строка)
    try:
        edit = win.EditControl(searchDepth=16)
        if edit.Exists(0, 0):
            return _value_of(edit)
    except Exception:
        pass
    return None


def _value_of(ctrl):
    """Значение элемента (ValuePattern), иначе его Name."""
    try:
        vp = ctrl.GetValuePattern()
        if vp and vp.Value:
            return vp.Value
    except Exception:
        pass
    try:
        return ctrl.Name or None
    except Exception:
        return None


def domain_from(text):
    """Вытащить домен из текста адресной строки. None, если не нашли."""
    if not text:
        return None
    m = _HOST_RE.search(text.strip())
    if not m:
        return None
    return m.group(1).lower().strip(".")


def _registrable(host):
    """Упрощённо свести домен к «основному» для сравнения.

    vk.com            -> vk.com
    mail.google.com   -> google.com
    site.co.uk        -> site.co.uk  (учтены популярные двойные зоны)
    """
    if not host:
        return None
    parts = host.lower().strip(".").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    two_level = {"co", "com", "org", "net", "gov", "edu", "ac"}
    if parts[-2] in two_level and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(site, url):
    """Подходит ли запись с адресом url к открытому сайту site."""
    a = _registrable(site)
    b = _registrable(domain_from(url) or url)
    if not a or not b:
        return False
    return a == b


def get_active_site():
    """Главная функция: домен сайта в активном браузере или None."""
    if not sys.platform.startswith("win"):
        return None
    try:
        hwnd = _active_browser_hwnd()
        if not hwnd:
            return None
        text = _read_address_text(hwnd)
        return domain_from(text)
    except Exception:
        return None
