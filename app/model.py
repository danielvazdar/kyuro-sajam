"""Oblik jednog očitanog računa i provjere koje se rade nad njim.

Isti oblik putuje od očitanja, kroz Danielove ispravke na ekranu, do eURA.txt —
zato se provjere računaju iz podataka, nikad ne spremaju uz njih.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Iznos = Annotated[Decimal, Field(ge=Decimal("-1000000"), le=Decimal("10000000"), decimal_places=2)]

STOPE: dict[str, Decimal] = {"5": Decimal("0.05"), "13": Decimal("0.13"), "25": Decimal("0.25")}
TOLERANCIJA = Decimal("0.02")  # zaokruživanje po stavkama na blagajni daje razliku od 1–2 centa


class Racun(BaseModel):
    """Jedan ulazni račun ili blagajnički račun (slip). Nepromjenjiv."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vrsta: Literal["racun", "slip"] = "racun"
    dobavljac: str = Field(default="", max_length=120)
    oib_dobavljaca: str = Field(default="", max_length=11)
    broj_racuna: str = Field(default="", max_length=60)
    datum_racuna: date
    datum_dospijeca: date | None = None
    ukupno: Iznos = Decimal("0")
    bez_pdv: Iznos = Decimal("0")
    osnovica5: Iznos = Decimal("0")
    pdv5: Iznos = Decimal("0")
    osnovica13: Iznos = Decimal("0")
    pdv13: Iznos = Decimal("0")
    osnovica25: Iznos = Decimal("0")
    pdv25: Iznos = Decimal("0")
    napomena: str = Field(default="", max_length=120)
    nesigurno: tuple[str, ...] = ()  # polja koja čitač nije mogao pouzdano pročitati

    @field_validator("oib_dobavljaca")
    @classmethod
    def _samo_znamenke(cls, vrijednost: str) -> str:
        return "".join(z for z in vrijednost if z.isdigit())


def oib_je_ispravan(oib: str) -> bool:
    """Kontrolna znamenka OIB-a, ISO 7064 MOD 11,10 — isti algoritam kao Porezna."""
    if len(oib) != 11 or not oib.isdigit():
        return False
    ostatak = 10
    for znamenka in oib[:10]:
        ostatak = (ostatak + int(znamenka)) % 10 or 10
        ostatak = (ostatak * 2) % 11
    return (11 - ostatak) % 10 == int(oib[10])


def upozorenja(racun: Racun) -> list[str]:
    """Što bi knjigovođa htio pogledati prije uvoza. Prazno = račun je čist."""
    nalazi: list[str] = []
    if not oib_je_ispravan(racun.oib_dobavljaca):
        nalazi.append("OIB dobavljača nije ispravan (kontrolna znamenka)")
    if not racun.broj_racuna.strip():
        nalazi.append("Nedostaje broj računa")
    zbroj = (
        racun.bez_pdv
        + racun.osnovica5 + racun.pdv5
        + racun.osnovica13 + racun.pdv13
        + racun.osnovica25 + racun.pdv25
    )
    if abs(zbroj - racun.ukupno) > TOLERANCIJA:
        nalazi.append(f"Stavke ({zbroj:.2f}) ne daju ukupni iznos ({racun.ukupno:.2f})")
    for stopa, faktor in STOPE.items():
        osnovica: Decimal = getattr(racun, f"osnovica{stopa}")
        pdv: Decimal = getattr(racun, f"pdv{stopa}")
        if abs(osnovica * faktor - pdv) > TOLERANCIJA:
            nalazi.append(f"PDV {stopa} % ne odgovara osnovici")
    if racun.datum_dospijeca and racun.datum_dospijeca < racun.datum_racuna:
        nalazi.append("Dospijeće je prije datuma računa")
    return nalazi
