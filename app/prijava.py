"""Prijava u aplikaciji umjesto nginx osnovne autentikacije.

14.10.: na iPhoneu, aplikacija s početnog zaslona čekala je 10–15 s na okvir osnovne
autentikacije i nije pamtila prijavu. Sada: ista lozinka kao demo (isti apr1 hash iz
.htpasswd-demo), potpisani kolačić na 60 dana, ljuska se otvara iz spremnika odmah.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import deque

from passlib.hash import apr_md5_crypt

KOLACIC = "sajam_prijava"
TRAJANJE_S = 60 * 24 * 3600
_POKUSAJA = 10  # krivih lozinki u prozoru — poslije toga čeka
_PROZOR_S = 15 * 60


def lozinka_ispravna(lozinka: str, apr1_hash: str) -> bool:
    if not lozinka or not apr1_hash:
        return False
    try:
        return bool(apr_md5_crypt.verify(lozinka, apr1_hash))
    except ValueError:
        return False


def _potpis(tajna: str, istek: int) -> str:
    return hmac.new(tajna.encode(), str(istek).encode(), hashlib.sha256).hexdigest()


def izdaj(tajna: str, sada: float | None = None) -> str:
    istek = int((sada or time.time()) + TRAJANJE_S)
    return f"{istek}.{_potpis(tajna, istek)}"


def vrijedi(token: str | None, tajna: str, sada: float | None = None) -> bool:
    if not token or "." not in token:
        return False
    istek_tekst, potpis = token.split(".", 1)
    if not istek_tekst.isdigit():
        return False
    istek = int(istek_tekst)
    if istek < (sada or time.time()):
        return False
    return hmac.compare_digest(potpis, _potpis(tajna, istek))


class Brana:
    """Ograničenje krivih pokušaja. Jedan proces, pa je memorija dovoljna."""

    def __init__(self, maks: int = _POKUSAJA, prozor_s: int = _PROZOR_S) -> None:
        self._maks = maks
        self._prozor = prozor_s
        self._promasaji: deque[float] = deque()
        self._brava = threading.Lock()

    def zatvorena(self) -> bool:
        sada = time.monotonic()
        with self._brava:
            while self._promasaji and sada - self._promasaji[0] > self._prozor:
                self._promasaji.popleft()
            return len(self._promasaji) >= self._maks

    def promasaj(self) -> None:
        with self._brava:
            self._promasaji.append(time.monotonic())
