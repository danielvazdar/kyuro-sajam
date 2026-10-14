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


DANIEL = "daniel"
_PROBA = "proba-"


def _potpis(tajna: str, poruka: str) -> str:
    return hmac.new(tajna.encode(), poruka.encode(), hashlib.sha256).hexdigest()


def subjekt_probe(kod: str) -> str:
    return f"{_PROBA}{kod}"


def kod_iz_subjekta(subjekt: str) -> str | None:
    return subjekt.removeprefix(_PROBA) if subjekt.startswith(_PROBA) else None


def izdaj(
    tajna: str, sada: float | None = None, *, subjekt: str = DANIEL, istek: int | None = None,
) -> str:
    """Token kolačića: `istek.subjekt.potpis`. Subjekt je Daniel ili probni kod posjetitelja."""
    istek = istek if istek is not None else int((sada or time.time()) + TRAJANJE_S)
    return f"{istek}.{subjekt}.{_potpis(tajna, f'{istek}.{subjekt}')}"


def procitaj(token: str | None, tajna: str, sada: float | None = None) -> str | None:
    """Subjekt iz valjanog, neisteklog tokena — inače None."""
    if not token:
        return None
    dijelovi = token.split(".")
    if len(dijelovi) == 2:
        # Tokeni izdani prije 14.10. (samo Daniel) — ne odjavljujemo ga usred sajma.
        istek_tekst, potpis = dijelovi
        subjekt, poruka = DANIEL, istek_tekst
    elif len(dijelovi) == 3:
        istek_tekst, subjekt, potpis = dijelovi
        poruka = f"{istek_tekst}.{subjekt}"
    else:
        return None
    if not istek_tekst.isdigit() or int(istek_tekst) < (sada or time.time()):
        return None
    return subjekt if hmac.compare_digest(potpis, _potpis(tajna, poruka)) else None


def vrijedi(token: str | None, tajna: str, sada: float | None = None) -> bool:
    return procitaj(token, tajna, sada) is not None


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
