"""bcrypt wrapper — single place to set the cost factor.

12 rounds ≈ 150ms/hash on modern hardware, the right ballpark for interactive
login latency.
"""
from __future__ import annotations

import bcrypt

_BCRYPT_ROUNDS = 12


def hash_password(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("empty password")
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plaintext: str, stored_hash: str) -> bool:
    if not plaintext or not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plaintext.encode(), stored_hash.encode())
    except ValueError:
        # Malformed hash in storage — treat as auth failure, not a 500.
        return False
