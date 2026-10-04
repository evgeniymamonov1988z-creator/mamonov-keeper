# -*- coding: utf-8 -*-
"""
Импорт паролей из браузеров на движке Chromium (Chrome, Edge,
Яндекс, Opera, Brave) и экспорт в CSV для импорта в браузер.

Расшифровка работает только на Windows и только под той же
учётной записью, в которой сохранены пароли (так устроено
шифрование Windows DPAPI). В интернет ничего не отправляется.
"""

import os
import csv
import json
import sys
import base64
import shutil
import sqlite3
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class BrowserError(Exception):
    """Ошибка импорта/экспорта браузерных паролей."""


# ---------- Windows DPAPI через ctypes (без сторонних библиотек) ----------
def _dpapi_decrypt(encrypted: bytes) -> bytes:
    """Расшифровать данные, зашифрованные Windows DPAPI."""
    if sys.platform != "win32":
        raise BrowserError("Расшифровка браузерных паролей работает только на Windows.")
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(encrypted, len(encrypted))
    blob_in = DATA_BLOB(len(encrypted),
                        ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out))
    if not ok:
        raise BrowserError("Не удалось расшифровать (DPAPI). Возможно, другая учётная запись.")
    data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return data


def _get_master_key(user_data_dir: str) -> bytes:
    """Достать AES-ключ браузера из файла Local State."""
    local_state = os.path.join(user_data_dir, "Local State")
    with open(local_state, "r", encoding="utf-8") as f:
        data = json.load(f)
    enc_key_b64 = data["os_crypt"]["encrypted_key"]
    enc_key = base64.b64decode(enc_key_b64)
    # первые 5 байт — префикс "DPAPI"
    return _dpapi_decrypt(enc_key[5:])


def _decrypt_password(blob: bytes, master_key: bytes) -> str:
    """Расшифровать один пароль из базы браузера."""
    if not blob:
        return ""
    prefix = blob[:3]
    if prefix in (b"v10", b"v11"):
        nonce = blob[3:15]
        ciphertext = blob[15:-16]
        tag = blob[-16:]
        aes = AESGCM(master_key)
        try:
            plain = aes.decrypt(nonce, ciphertext + tag, None)
            return plain.decode("utf-8", "replace")
        except Exception:
            return ""
    # старый формат — напрямую через DPAPI
    try:
        return _dpapi_decrypt(blob).decode("utf-8", "replace")
    except Exception:
        return ""


# ---------- поиск установленных браузеров ----------
def _candidate_browsers():
    """Список (название, папка User Data) для известных Chromium-браузеров."""
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    paths = [
        ("Google Chrome", os.path.join(local, "Google", "Chrome", "User Data")),
        ("Microsoft Edge", os.path.join(local, "Microsoft", "Edge", "User Data")),
        ("Яндекс.Браузер", os.path.join(local, "Yandex", "YandexBrowser", "User Data")),
        ("Brave", os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")),
        ("Opera", os.path.join(roaming, "Opera Software", "Opera Stable")),
        ("Opera GX", os.path.join(roaming, "Opera Software", "Opera GX Stable")),
        ("Chromium", os.path.join(local, "Chromium", "User Data")),
    ]
    return [(name, p) for name, p in paths if p and os.path.isdir(p)]


def list_browsers():
    """Названия найденных браузеров."""
    return [name for name, _ in _candidate_browsers()]


def _profile_dirs(user_data_dir: str):
    """Папки профилей (Default, Profile 1, ...), где есть Login Data."""
    found = []
    for entry in ["Default"] + ["Profile %d" % i for i in range(1, 11)] + ["."]:
        d = os.path.join(user_data_dir, entry)
        if os.path.isfile(os.path.join(d, "Login Data")):
            found.append(d)
    return found


def _read_logins(login_data_path: str):
    """Прочитать таблицу logins из копии файла (файл может быть занят)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    try:
        shutil.copy2(login_data_path, tmp.name)
        con = sqlite3.connect(tmp.name)
        try:
            cur = con.execute(
                "SELECT origin_url, username_value, password_value FROM logins")
            rows = cur.fetchall()
        finally:
            con.close()
        return rows
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def import_passwords():
    """Собрать и расшифровать пароли из всех найденных браузеров.

    Возвращает список записей в формате «Ключницы».
    """
    if sys.platform != "win32":
        raise BrowserError("Импорт из браузера работает только на Windows.")
    browsers = _candidate_browsers()
    if not browsers:
        raise BrowserError("Не найдено ни одного поддерживаемого браузера.")
    entries = []
    for name, user_data_dir in browsers:
        try:
            master_key = _get_master_key(user_data_dir)
        except Exception:
            continue
        for prof in _profile_dirs(user_data_dir):
            try:
                rows = _read_logins(os.path.join(prof, "Login Data"))
            except Exception:
                continue
            for url, login, pw_blob in rows:
                pw = _decrypt_password(pw_blob, master_key)
                if not (login or pw):
                    continue
                title = url or login
                entries.append({
                    "title": title,
                    "login": login or "",
                    "password": pw,
                    "url": url or "",
                    "note": "импорт из %s" % name,
                })
    return entries


# ---------- экспорт в CSV для браузера ----------
def export_csv(entries, path: str):
    """Сохранить записи в CSV в формате, который понимают
    браузеры (Chrome/Edge/Яндекс): name,url,username,password,note.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "url", "username", "password", "note"])
        for e in entries:
            writer.writerow([
                e.get("title", ""),
                e.get("url", ""),
                e.get("login", ""),
                e.get("password", ""),
                e.get("note", ""),
            ])
    return len(entries)
