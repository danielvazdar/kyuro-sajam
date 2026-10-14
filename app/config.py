"""Postavke iz okoline. Nedostaje li ključ, servis ne starta — odmah, ne pred posjetiteljem."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_OBAVEZNO = (
    "ANTHROPIC_API_KEY", "BREVO_API_KEY", "ATTIO_API_KEY", "SAJAM_LOZINKA_HASH", "SAJAM_TAJNA",
)


@dataclass(frozen=True)
class Postavke:
    brevo_api_key: str
    attio_api_key: str
    data_dir: Path
    posiljatelj_email: str
    posiljatelj_ime: str
    odgovor_na: str
    kampanja: str
    test_adrese: frozenset[str]
    lozinka_hash: str  # apr1 hash iz /etc/nginx/.htpasswd-demo — ista lozinka kao demo
    tajna: str  # potpisuje kolačić prijave

    @classmethod
    def iz_okoline(cls) -> Postavke:
        nedostaje = [kljuc for kljuc in _OBAVEZNO if not os.getenv(kljuc)]
        if nedostaje:
            raise RuntimeError(f"Nedostaju varijable okoline: {', '.join(nedostaje)}")
        return cls(
            brevo_api_key=os.environ["BREVO_API_KEY"],
            attio_api_key=os.environ["ATTIO_API_KEY"],
            data_dir=Path(os.getenv("DATA_DIR", "./data")).expanduser(),
            posiljatelj_email=os.getenv("SENDER_EMAIL", "sajam@mail.kyuro.tech"),
            posiljatelj_ime=os.getenv("SENDER_NAME", "Kyuro"),
            odgovor_na=os.getenv("REPLY_TO", "hello@kyuro.tech"),
            kampanja=os.getenv("KAMPANJA", "Accept sajam 2026"),
            # Adrese s kojih Daniel testira prije sajma: mail ide, ali u Attio ne ulaze kao lead.
            test_adrese=frozenset(
                a.strip().lower() for a in os.getenv("TEST_ADRESE", "").split(",") if a.strip()
            ),
            lozinka_hash=os.environ["SAJAM_LOZINKA_HASH"],
            tajna=os.environ["SAJAM_TAJNA"],
        )
