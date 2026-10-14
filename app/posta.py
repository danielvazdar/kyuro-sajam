"""Mail posjetitelju: fotografija, eURA.txt i pregled u CSV-u, preko Brevo transakcijskog API-ja."""

from __future__ import annotations

import base64
import csv
import io
import logging
from collections.abc import Sequence

import requests

from app.config import Postavke
from app.model import Racun, upozorenja
from app.tekstovi import (
    MAIL_NASLOV,
    mail_html,
)

logger = logging.getLogger(__name__)

SEND_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_S = 30


class GreskaSlanja(RuntimeError):
    """Mail nije otišao. Poruka je za ekran, na hrvatskom."""


def pregled_csv(racuni: Sequence[Racun]) -> bytes:
    """Pregled za Excel: točka-zarez i BOM, jer hrvatski Excel inače sve strpa u stupac A."""
    izlaz = io.StringIO()
    pisac = csv.writer(izlaz, delimiter=";", lineterminator="\r\n")
    pisac.writerow([
        "Vrsta", "Dobavljač", "OIB", "Broj računa", "Datum", "Dospijeće", "Ukupno",
        "Bez PDV-a", "Osnovica 5%", "PDV 5%", "Osnovica 13%", "PDV 13%",
        "Osnovica 25%", "PDV 25%", "Napomena", "Za provjeru",
    ])
    for r in racuni:
        pisac.writerow([
            "Slip" if r.vrsta == "slip" else "Račun", r.dobavljac, r.oib_dobavljaca,
            r.broj_racuna, r.datum_racuna.strftime("%d.%m.%Y."),
            r.datum_dospijeca.strftime("%d.%m.%Y.") if r.datum_dospijeca else "",
            *(f"{iznos:.2f}".replace(".", ",") for iznos in (
                r.ukupno, r.bez_pdv, r.osnovica5, r.pdv5, r.osnovica13, r.pdv13,
                r.osnovica25, r.pdv25,
            )),
            r.napomena, " · ".join(upozorenja(r)),
        ])
    return ("﻿" + izlaz.getvalue()).encode("utf-8")


def _privitak(ime: str, sadrzaj: bytes) -> dict[str, str]:
    return {"name": ime, "content": base64.b64encode(sadrzaj).decode("ascii")}


def sastavi(
    postavke: Postavke,
    *,
    primatelj: str,
    ime: str,
    racuni: Sequence[Racun],
    eura: str,
    fotografije: Sequence[bytes],
) -> dict[str, object]:
    privitci = [
        _privitak("eURA.txt", eura.encode("ascii")),
        _privitak("pregled-racuna.csv", pregled_csv(racuni)),
    ]
    if len(fotografije) == 1:
        privitci.append(_privitak("fotografija.jpg", fotografije[0]))
    else:
        privitci.extend(
            _privitak(f"fotografija-{broj}.jpg", slika)
            for broj, slika in enumerate(fotografije, start=1)
        )
    return {
        "sender": {"email": postavke.posiljatelj_email, "name": postavke.posiljatelj_ime},
        "to": [{"email": primatelj, **({"name": ime} if ime else {})}],
        "replyTo": {"email": postavke.odgovor_na, "name": "Daniel Vazdar, Kyuro"},
        "subject": MAIL_NASLOV,
        "htmlContent": mail_html(
            ime=ime, racuni=racuni, email=primatelj, fotografija=len(fotografije),
        ),
        "attachment": privitci,
        "tags": ["sajam"],
    }


def posalji(postavke: Postavke, poruka: dict[str, object]) -> str:
    """Pošalji i vrati Brevo messageId. 2xx znači da je Brevo PRIMIO mail, ne da je stigao."""
    try:
        odgovor = requests.post(
            SEND_URL,
            json=poruka,
            headers={"api-key": postavke.brevo_api_key, "accept": "application/json"},
            timeout=_TIMEOUT_S,
        )
    except requests.RequestException as greska:
        logger.warning("posta: Brevo nedostupan: %s", type(greska).__name__)
        raise GreskaSlanja("Nema veze do poslužitelja pošte. Pokušajte ponovno.") from greska
    if odgovor.status_code >= 300:
        # Tijelo greške ne sadrži ključ, ali ga ipak skraćujemo — ne treba nam cijelo.
        logger.error("posta: Brevo %s %.300s", odgovor.status_code, odgovor.text)
        raise GreskaSlanja("Mail nije poslan. Provjerite adresu i pokušajte ponovno.")
    return str(odgovor.json().get("messageId", ""))
