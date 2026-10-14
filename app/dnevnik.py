"""Dnevnik leadova: jedan JSON redak po posjetitelju, upisan PRIJE slanja maila i Attia.

Ako Brevo ili Attio padnu usred sajma, lead je i dalje ovdje — `scripts/attio_dopuni.py`
ga kasnije prebaci. Ovo je jedini zapis koji ne ovisi ni o kome izvana.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_brava = threading.Lock()


def upisi(data_dir: Path, zapis: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    redak = json.dumps(
        {"vrijeme": datetime.now(UTC).isoformat(), **zapis},
        ensure_ascii=False, default=str,
    )
    putanja = data_dir / "leadovi.jsonl"
    with _brava, putanja.open("a", encoding="utf-8") as datoteka:
        datoteka.write(redak + "\n")
        datoteka.flush()
        os.fsync(datoteka.fileno())


def procitaj_sve(data_dir: Path) -> list[dict[str, Any]]:
    putanja = data_dir / "leadovi.jsonl"
    if not putanja.exists():
        return []
    with putanja.open(encoding="utf-8") as datoteka:
        return [json.loads(redak) for redak in datoteka if redak.strip()]
