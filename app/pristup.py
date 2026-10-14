"""Probni pristup: svaki posjetitelj kojem Daniel pokaže aplikaciju dobije osobni kod na 7 dana.

Kod (npr. KQ7M-4RTX) stiže mailom dobrodošlice. Kod, a ne samo poveznica, jer iPhone aplikaciji
s početnog zaslona ne daje kolačiće iz Safarija — tamo se kod upiše jednom na ekranu prijave.

Zapis je jedna JSON datoteka (data/pristupi.json). Jedan proces, jedna brava — dovoljno za sajam.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROBNI_DANI = 7
MAKS_CITANJA = 20  # granica troška po probi: ~20 fotografija ≈ manje od 0,50 € čitača
_ZNAKOVI = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bez 0/O, 1/I — kod se prepisuje s mobitela
_DULJINA = 8


@dataclass(frozen=True)
class Pristup:
    kod: str  # normaliziran: 8 znakova, bez crtice
    email: str
    ime: str
    istek: str  # ISO vrijeme u UTC
    citanja: int = 0

    @property
    def istek_dt(self) -> datetime:
        return datetime.fromisoformat(self.istek)

    def vrijedi(self, sada: datetime | None = None) -> bool:
        return (sada or datetime.now(UTC)) < self.istek_dt

    @property
    def za_prikaz(self) -> str:
        return f"{self.kod[:4]}-{self.kod[4:]}"


def normaliziraj(kod: str) -> str:
    return "".join(z for z in kod.upper() if z in _ZNAKOVI)


def je_kod(tekst: str) -> bool:
    """Izgleda li upis kao pristupni kod (a ne Danielova lozinka)."""
    return len(normaliziraj(tekst)) == _DULJINA and len(tekst.strip()) <= _DULJINA + 1


class Spremiste:
    def __init__(self, data_dir: Path) -> None:
        self._putanja = data_dir / "pristupi.json"
        self._brava = threading.Lock()

    def _citaj(self) -> dict[str, Pristup]:
        if not self._putanja.exists():
            return {}
        sirovo = json.loads(self._putanja.read_text(encoding="utf-8"))
        return {kod: Pristup(**zapis) for kod, zapis in sirovo.items()}

    def _pisi(self, pristupi: dict[str, Pristup]) -> None:
        self._putanja.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Atomično: privremena datoteka pa zamjena — pad usred pisanja ne smije pojesti sve kodove.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self._putanja.parent, delete=False,
        ) as privremena:
            json.dump({k: asdict(v) for k, v in pristupi.items()}, privremena, ensure_ascii=False)
        os.replace(privremena.name, self._putanja)

    def izdaj(self, *, email: str, ime: str, sada: datetime | None = None) -> Pristup:
        """Novi kod, ili postojeći važeći za istu adresu (isti posjetitelj dvaput = jedan kod)."""
        sada = sada or datetime.now(UTC)
        with self._brava:
            pristupi = self._citaj()
            for postojeci in pristupi.values():
                if postojeci.email == email and postojeci.vrijedi(sada):
                    return postojeci
            kod = "".join(secrets.choice(_ZNAKOVI) for _ in range(_DULJINA))
            while kod in pristupi:
                kod = "".join(secrets.choice(_ZNAKOVI) for _ in range(_DULJINA))
            novi = Pristup(kod=kod, email=email, ime=ime,
                           istek=(sada + timedelta(days=PROBNI_DANI)).isoformat())
            self._pisi({**pristupi, kod: novi})
            return novi

    def po_kodu(self, kod: str) -> Pristup | None:
        with self._brava:
            return self._citaj().get(normaliziraj(kod))

    def zabiljezi_citanje(self, kod: str) -> bool:
        """Potroši jedno čitanje. False = proba je potrošena ili istekla."""
        with self._brava:
            pristupi = self._citaj()
            pristup = pristupi.get(kod)
            if pristup is None or not pristup.vrijedi() or pristup.citanja >= MAKS_CITANJA:
                return False
            self._pisi({**pristupi, kod: replace(pristup, citanja=pristup.citanja + 1)})
            return True
