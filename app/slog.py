"""eURA.txt — knjiga ulaznih računa za Synesis (Pupilla), osnovna verzija.

Preneseno 1:1 iz `kyuro-demo/src/lib/slog/{fixed,eura}.ts`; test `test_slog.py` drži iste
položaje polja kao TS testovi. Ako se jedno mijenja, mijenja se i drugo.

Redoslijed i širine po `SlogKnjizenje.pdf`:
  OIB 11 L · Šifra 7 D · Broj računa 15 L · Datum računa 8 · Datum dospijeća 8 ·
  Ukupno 14 D · Ne podliježe PDV-u 14 D · osnovica+PDV 5 %, 13 %, 25 % (6 × 14 D) · Napomena 50.
Širina retka: 211 znakova, svaki redak završava CR+LF.

⚠️ Kodna stranica u specifikaciji NIJE navedena, a polja su fiksne širine u BAJTOVIMA —
jedan „č" u UTF-8 pomakne svako polje iza sebe. Zato sve ide u čisti ASCII.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.model import Racun

KRAJ_RETKA = "\r\n"
SIRINA_RETKA_EURA = 211

_ZAMJENE = {
    "đ": "d", "Đ": "D",
    "—": "-", "–": "-", "−": "-",
    "„": '"', "“": '"', "”": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'",
    "…": "...", " ": " ",
}
_NIJE_ASCII = re.compile(r"[^ -~]")


def u_ascii(tekst: str) -> str:
    """Sve u ASCII 0x20–0x7E; dijakritike bez kvačica, ostatak ispada."""
    zamijenjeno = _NIJE_ASCII.sub(lambda z: _ZAMJENE.get(z.group(0), z.group(0)), tekst)
    bez_kvacica = "".join(
        znak for znak in unicodedata.normalize("NFD", zamijenjeno)
        if not unicodedata.combining(znak)
    )
    return _NIJE_ASCII.sub("", bez_kvacica)


def polje_lijevo(vrijednost: str, sirina: int) -> str:
    # Spec: predugačko se REŽE, ne prelama.
    return u_ascii(vrijednost).strip()[:sirina].ljust(sirina)


def polje_desno(vrijednost: str, sirina: int) -> str:
    return u_ascii(vrijednost).strip()[:sirina].rjust(sirina)


def polje_iznos(iznos: Decimal, sirina: int) -> str:
    return str(iznos.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)).rjust(sirina)


def polje_datum(datum: date) -> str:
    return datum.strftime("%d%m%Y")


def redak_eura(racun: Racun) -> str:
    return "".join([
        polje_lijevo(racun.oib_dobavljaca, 11),
        polje_desno("", 7),  # šifra nije obavezna — Synesis tada veže po OIB-u
        polje_lijevo(racun.broj_racuna, 15),
        polje_datum(racun.datum_racuna),
        polje_datum(racun.datum_dospijeca or racun.datum_racuna),
        polje_iznos(racun.ukupno, 14),
        polje_iznos(racun.bez_pdv, 14),
        polje_iznos(racun.osnovica5, 14),
        polje_iznos(racun.pdv5, 14),
        polje_iznos(racun.osnovica13, 14),
        polje_iznos(racun.pdv13, 14),
        polje_iznos(racun.osnovica25, 14),
        polje_iznos(racun.pdv25, 14),
        polje_lijevo(racun.napomena or racun.dobavljac, 50),
    ])


def datoteka_eura(racuni: Iterable[Racun]) -> str:
    return "".join(redak_eura(racun) + KRAJ_RETKA for racun in racuni)
