# -*- coding: utf-8 -*-
"""Генератор надёжных паролей."""

import secrets
import string

_LOWER = string.ascii_lowercase
_UPPER = string.ascii_uppercase
_DIGITS = string.digits
_SYMBOLS = "!@#$%^&*()-_=+[]{}?"


def generate(length: int = 16,
             use_upper: bool = True,
             use_digits: bool = True,
             use_symbols: bool = True) -> str:
    """Сгенерировать случайный пароль.

    Гарантирует, что в пароле есть хотя бы по одному символу
    каждого включённого набора. Использует secrets —
    криптографически стойкий генератор случайных чисел.
    """
    if length < 4:
        length = 4

    pools = [_LOWER]
    if use_upper:
        pools.append(_UPPER)
    if use_digits:
        pools.append(_DIGITS)
    if use_symbols:
        pools.append(_SYMBOLS)

    alphabet = "".join(pools)

    # по одному символу из каждого набора
    chars = [secrets.choice(pool) for pool in pools]
    # остальное — из общего алфавита
    while len(chars) < length:
        chars.append(secrets.choice(alphabet))
    # перемешать, чтобы обязательные символы не стояли в начале
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def strength(password: str) -> str:
    """Грубая оценка надёжности пароля."""
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if any(c in _LOWER for c in password) and any(c in _UPPER for c in password):
        score += 1
    if any(c in _DIGITS for c in password):
        score += 1
    if any(c in _SYMBOLS for c in password):
        score += 1
    if score <= 2:
        return "слабый"
    if score <= 4:
        return "средний"
    return "надёжный"
