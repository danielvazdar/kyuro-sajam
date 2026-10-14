"""Čitač: jedna fotografija lista papira → popis računa i slipova.

Jedan poziv Claudeu (vision) sa strukturiranim izlazom. Model ne računa ništa što se
može provjeriti kodom: zbrojevi, PDV i kontrolna znamenka OIB-a provjeravaju se u
`model.upozorenja`, ne vjeruje im se na riječ.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal

import anthropic
from anthropic.types.beta import (
    BetaImageBlockParam,
    BetaMessageParam,
    BetaOutputConfigParam,
    BetaTextBlockParam,
)
from pydantic import ValidationError

from app.model import Racun

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
# Na sajmu posjetitelj čeka pred štandom: brzina je dio demonstracije.
EFFORT: Final = "medium"

_POLJA_IZNOSA = (
    "ukupno", "bez_pdv", "osnovica5", "pdv5", "osnovica13", "pdv13", "osnovica25", "pdv25",
)

_SHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["dokumenti"],
    "properties": {
        "dokumenti": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "vrsta", "dobavljac", "oib_dobavljaca", "broj_racuna", "datum_racuna",
                    "datum_dospijeca", *_POLJA_IZNOSA, "napomena", "nesigurno",
                ],
                "properties": {
                    "vrsta": {"type": "string", "enum": ["racun", "slip"]},
                    "dobavljac": {"type": "string"},
                    "oib_dobavljaca": {"type": "string"},
                    "broj_racuna": {"type": "string"},
                    "datum_racuna": {"type": "string", "description": "YYYY-MM-DD"},
                    "datum_dospijeca": {"type": "string", "description": "YYYY-MM-DD ili prazno"},
                    **{polje: {"type": "string", "description": "iznos u EUR, npr. 12.50"}
                       for polje in _POLJA_IZNOSA},
                    "napomena": {"type": "string"},
                    "nesigurno": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}

_UPUTA = """Na fotografiji je list papira na koji je zalijepljeno nekoliko hrvatskih računa \
(R1/R2 računi dobavljača) i blagajničkih računa (slipova s blagajne). Pronađi SVAKI dokument \
na fotografiji i za svaki izvuci podatke za knjigu ulaznih računa (URA).

Pravila:
- vrsta: "slip" za blagajnički/fiskalni račun s blagajne, inače "racun".
- dobavljac: naziv izdavatelja računa (ne kupca). oib_dobavljaca: 11 znamenki OIB-a \
IZDAVATELJA, točno kako piše; ako ga ne vidiš, ostavi prazno.
- broj_racuna: broj računa točno kako piše (npr. "123/P1/1").
- datum_racuna i datum_dospijeca u obliku YYYY-MM-DD; ako dospijeća nema, ostavi prazno.
- Iznosi su u eurima, decimalna točka, dvije decimale, bez oznake valute.
- Rasporedi osnovicu i PDV po stopama 5 %, 13 % i 25 % prema rekapitulaciji poreza na \
računu. Iznos koji ne podliježe PDV-u (npr. povratna naknada, neoporezive stavke) ide u bez_pdv. \
Stopa koje nema na računu ima "0.00".
- ukupno: ukupni iznos za plaćanje.
- napomena: kratko što je kupljeno (do 40 znakova, npr. "Gorivo", "Uredski materijal").
- nesigurno: nazivi polja (iz ove sheme) koja nisu jasno čitljiva ili si ih morao pretpostaviti. \
Budi iskren: bolje označiti polje nego pogoditi.
- Ne izmišljaj podatke kojih nema na slici. Ako dokument nije račun (npr. reklama), preskoči ga."""


class GreskaCitanja(RuntimeError):
    """Očitanje nije uspjelo — poruka je za Daniela na ekranu, na hrvatskom."""


def _datum(tekst: str) -> date | None:
    try:
        return date.fromisoformat(tekst.strip()) if tekst.strip() else None
    except ValueError:
        return None


def _iznos(tekst: str) -> Decimal:
    ocisceno = tekst.strip().replace(" ", "").replace("€", "").replace(",", ".") or "0"
    try:
        return Decimal(ocisceno).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def u_racun(sirovo: dict[str, Any]) -> Racun | None:
    """Sirovi izlaz modela → Racun. Neočitljivo polje postaje prazno i označeno, ne pad."""
    nesigurno = {str(p) for p in sirovo.get("nesigurno", [])}
    datum_racuna = _datum(str(sirovo.get("datum_racuna", "")))
    if datum_racuna is None:
        nesigurno.add("datum_racuna")
        datum_racuna = date.today()
    iznosi = {polje: _iznos(str(sirovo.get(polje, "0"))) for polje in _POLJA_IZNOSA}
    try:
        return Racun(
            vrsta="slip" if sirovo.get("vrsta") == "slip" else "racun",
            dobavljac=str(sirovo.get("dobavljac", ""))[:120],
            oib_dobavljaca=str(sirovo.get("oib_dobavljaca", ""))[:20],
            broj_racuna=str(sirovo.get("broj_racuna", ""))[:60],
            datum_racuna=datum_racuna,
            datum_dospijeca=_datum(str(sirovo.get("datum_dospijeca", ""))),
            napomena=str(sirovo.get("napomena", ""))[:120],
            nesigurno=tuple(sorted(nesigurno)),
            **iznosi,
        )
    except ValidationError:
        logger.warning("citac: dokument odbačen, ne prolazi validaciju: %s", sirovo)
        return None


VrstaSlike = Literal["image/jpeg", "image/png", "image/webp"]


def procitaj(slika: bytes, media_type: VrstaSlike, klijent: anthropic.Anthropic) -> list[Racun]:
    """Pošalji fotografiju Claudeu i vrati očitane račune."""
    postavke_izlaza: BetaOutputConfigParam = {
        "effort": EFFORT,
        "format": {"type": "json_schema", "schema": _SHEMA},
    }
    fotografija: BetaImageBlockParam = {"type": "image", "source": {
        "type": "base64",
        "media_type": media_type,
        "data": base64.standard_b64encode(slika).decode("ascii"),
    }}
    uputa: BetaTextBlockParam = {"type": "text", "text": _UPUTA}
    poruke: list[BetaMessageParam] = [{"role": "user", "content": [fotografija, uputa]}]
    try:
        odgovor = klijent.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config=postavke_izlaza,
            messages=poruke,
        )
    except anthropic.RateLimitError as greska:
        logger.warning("citac: rate limit (%s)", greska.message)
        raise GreskaCitanja("Previše zahtjeva odjednom — pokušajte ponovno za minutu.") from greska
    except anthropic.APIConnectionError as greska:
        logger.warning("citac: nema veze s API-jem: %s", greska)
        raise GreskaCitanja("Nema internetske veze do čitača. Provjerite mrežu.") from greska
    except anthropic.APIStatusError as greska:
        logger.error("citac: API %s %s (request %s)", greska.status_code, greska.message,
                     greska.response.headers.get("request-id"))
        raise GreskaCitanja("Čitač trenutno ne radi. Pokušajte ponovno.") from greska

    if odgovor.stop_reason == "refusal":
        logger.error("citac: refusal %s", odgovor.stop_details)
        raise GreskaCitanja("Čitač je odbio ovu fotografiju. Pokušajte drugu.")
    if odgovor.stop_reason == "max_tokens":
        raise GreskaCitanja("Na fotografiji je previše dokumenata za jedno čitanje.")

    tekst = next((blok.text for blok in odgovor.content if blok.type == "text"), "")
    try:
        dokumenti = json.loads(tekst)["dokumenti"]
    except (json.JSONDecodeError, KeyError, TypeError) as greska:
        logger.error("citac: neočekivan izlaz: %.500s", tekst)
        raise GreskaCitanja("Čitač je vratio nečitljiv odgovor. Pokušajte ponovno.") from greska

    racuni = [r for r in (u_racun(d) for d in dokumenti if isinstance(d, dict)) if r]
    logger.info("citac: %d dokumenata, tokeni ulaz=%s izlaz=%s", len(racuni),
                odgovor.usage.input_tokens, odgovor.usage.output_tokens)
    return racuni
