# -*- coding: utf-8 -*-
"""
Ключница — хранилище паролей (шифрование и работа с файлом).

Файл хранилища (vault.dat) устроен так:
    [MAGIC(8)] [VERSION(1)] [SALT(16)] [FERNET-токен ...]
Мастер-пароль нигде не сохраняется: из него и соли (SALT)
выводится ключ шифрования через PBKDF2 (200000 итераций).
Без правильного мастер-пароля файл — нечитаемая «каша».
"""

import os
import json
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"KLYUCHN1"      # метка «наш» файл
_VERSION = 1
_SALT_LEN = 16
_ITERATIONS = 200_000


class WrongPassword(Exception):
    """Неверный мастер-пароль или повреждённый файл."""


class BadFile(Exception):
    """Это не файл хранилища «Ключницы»."""


def _derive_key(master_password: str, salt: bytes) -> bytes:
    """Получить 32-байтный ключ Fernet из мастер-пароля и соли."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    raw = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def read_vault_file(path: str, master_password: str) -> list:
    """Прочитать записи из любого файла-архива «Ключницы».

    Возвращает список записей. Бросает BadFile, если это не наш файл,
    и WrongPassword, если пароль не подходит.
    """
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:len(MAGIC)] != MAGIC:
        raise BadFile("Это не файл-архив «Ключницы».")
    pos = len(MAGIC)
    version = blob[pos]
    pos += 1
    if version != _VERSION:
        raise BadFile("Неподдерживаемая версия файла.")
    salt = blob[pos:pos + _SALT_LEN]
    pos += _SALT_LEN
    token = blob[pos:]
    fernet = Fernet(_derive_key(master_password, salt))
    try:
        data = fernet.decrypt(token)
    except InvalidToken:
        raise WrongPassword("Неверный мастер-пароль.")
    return json.loads(data.decode("utf-8"))


class Vault:
    """Одно зашифрованное хранилище паролей."""

    def __init__(self, path: str):
        self.path = path
        self._fernet = None          # Fernet, готовый шифровать/дешифровать
        self._salt = None
        self.entries = []            # список записей (dict)

    # ---------- состояние ----------
    def exists(self) -> bool:
        return os.path.exists(self.path)

    @property
    def is_open(self) -> bool:
        return self._fernet is not None

    # ---------- создание / открытие ----------
    def create(self, master_password: str) -> None:
        """Создать новое пустое хранилище с мастер-паролем."""
        self._salt = os.urandom(_SALT_LEN)
        self._fernet = Fernet(_derive_key(master_password, self._salt))
        self.entries = []
        self.save()

    def open(self, master_password: str) -> None:
        """Открыть существующее хранилище."""
        with open(self.path, "rb") as f:
            blob = f.read()
        if blob[:len(MAGIC)] != MAGIC:
            raise BadFile("Это не файл хранилища «Ключницы».")
        pos = len(MAGIC)
        version = blob[pos]
        pos += 1
        if version != _VERSION:
            raise BadFile("Неподдерживаемая версия файла.")
        self._salt = blob[pos:pos + _SALT_LEN]
        pos += _SALT_LEN
        token = blob[pos:]
        fernet = Fernet(_derive_key(master_password, self._salt))
        try:
            data = fernet.decrypt(token)
        except InvalidToken:
            raise WrongPassword("Неверный мастер-пароль.")
        self._fernet = fernet
        self.entries = json.loads(data.decode("utf-8"))

    def change_master_password(self, new_password: str) -> None:
        """Сменить мастер-пароль (новая соль + перешифровка)."""
        if not self.is_open:
            raise RuntimeError("Хранилище не открыто.")
        self._salt = os.urandom(_SALT_LEN)
        self._fernet = Fernet(_derive_key(new_password, self._salt))
        self.save()

    # ---------- сохранение ----------
    def save(self) -> None:
        """Зашифровать и записать хранилище на диск (атомарно)."""
        if not self.is_open:
            raise RuntimeError("Хранилище не открыто.")
        plain = json.dumps(self.entries, ensure_ascii=False).encode("utf-8")
        token = self._fernet.encrypt(plain)
        blob = MAGIC + bytes([_VERSION]) + self._salt + token
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)   # атомарная замена — не потеряем данные

    # ---------- работа с записями ----------
    def add(self, entry: dict) -> None:
        self.entries.append(entry)
        self.save()

    def update(self, index: int, entry: dict) -> None:
        self.entries[index] = entry
        self.save()

    def delete(self, index: int) -> None:
        del self.entries[index]
        self.save()

    def export_backup(self, dest: str) -> None:
        """Сохранить закрытый (зашифрованный) архив со всеми записями.

        Архив защищён текущим мастер-паролем (тот же формат, что и vault.dat).
        """
        if not self.is_open:
            raise RuntimeError("Хранилище не открыто.")
        plain = json.dumps(self.entries, ensure_ascii=False).encode("utf-8")
        token = self._fernet.encrypt(plain)
        blob = MAGIC + bytes([_VERSION]) + self._salt + token
        with open(dest, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())

    def lock(self) -> None:
        """Забыть ключ из памяти (блокировка)."""
        self._fernet = None
        self.entries = []
