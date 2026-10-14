"""Lead u Attio: osoba (po mailu) → tvrtka (ako je upisana) → posao u fazi „Lead" → bilješka.

Pravila preuzeta iz webinar-funnela (`core/app/services/attio_crm.py`), jer vrijede za isti CRM:
- Attio jedinstvenost drži na MAILU. Postojeću osobu se ne prepisuje — samo se dodaje bilješka.
- Posao je jedan po osobi; ako već postoji, ne otvara se novi.
- Vrijednost posla ostaje prazna: ništa nije dogovoreno.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

API = "https://api.attio.com/v2"
_TIMEOUT_S = 20
FAZA_NOVI = "Lead"


class GreskaAttio(RuntimeError):
    pass


class Attio:
    def __init__(self, api_key: str) -> None:
        self._sesija = requests.Session()
        self._sesija.headers.update({"Authorization": f"Bearer {api_key}"})

    def _zahtjev(self, metoda: str, putanja: str, tijelo: dict[str, Any] | None = None) -> Any:
        try:
            odgovor = self._sesija.request(metoda, API + putanja, json=tijelo, timeout=_TIMEOUT_S)
        except requests.RequestException as greska:
            raise GreskaAttio(f"{metoda} {putanja}: {type(greska).__name__}") from greska
        if odgovor.status_code >= 300:
            raise GreskaAttio(f"{metoda} {putanja}: {odgovor.status_code} {odgovor.text[:300]}")
        return odgovor.json()

    def trazi(self, objekt: str, filtar: dict[str, Any]) -> list[dict[str, Any]]:
        tijelo = {"filter": filtar, "limit": 1}
        return list(self._zahtjev("POST", f"/objects/{objekt}/records/query", tijelo)["data"])

    def stvori(self, objekt: str, vrijednosti: dict[str, Any]) -> str:
        zapis = self._zahtjev("POST", f"/objects/{objekt}/records",
                              {"data": {"values": vrijednosti}})["data"]
        return str(zapis["id"]["record_id"])

    def azuriraj(self, objekt: str, zapis_id: str, vrijednosti: dict[str, Any]) -> None:
        self._zahtjev("PATCH", f"/objects/{objekt}/records/{zapis_id}",
                      {"data": {"values": vrijednosti}})

    def vlasnik(self) -> str | None:
        clanovi = self._zahtjev("GET", "/workspace_members")["data"]
        return str(clanovi[0]["id"]["workspace_member_id"]) if len(clanovi) == 1 else None

    def biljeska(self, objekt: str, zapis_id: str, naslov: str, sadrzaj: str) -> None:
        self._zahtjev("POST", "/notes", {"data": {
            "parent_object": objekt, "parent_record_id": zapis_id,
            "title": naslov, "format": "plaintext", "content": sadrzaj,
        }})


def _ref(objekt: str, zapis_id: str) -> list[dict[str, str]]:
    return [{"target_object": objekt, "target_record_id": zapis_id}]


def _osoba(attio: Attio, *, email: str, ime: str, kampanja: str) -> tuple[str, bool]:
    """(id osobe, je li nova). Postojeća osoba se ne dira — samo se pronađe."""
    nadjeni = attio.trazi("people", {"email_addresses": email})
    if nadjeni:
        return str(nadjeni[0]["id"]["record_id"]), False
    vrijednosti: dict[str, Any] = {
        "email_addresses": [email],
        "kyuro_first_campaign": kampanja,
    }
    if ime:
        dijelovi = ime.split(maxsplit=1)
        vrijednosti["name"] = [{
            "first_name": dijelovi[0],
            "last_name": dijelovi[1] if len(dijelovi) > 1 else "",
            "full_name": ime,
        }]
    return attio.stvori("people", vrijednosti), True


def _tvrtka(attio: Attio, naziv: str) -> str | None:
    naziv = " ".join(naziv.split())
    if not naziv:
        return None
    nadjene = attio.trazi("companies", {"name": {"$eq": naziv}})
    return str(nadjene[0]["id"]["record_id"]) if nadjene else attio.stvori("companies",
                                                                            {"name": naziv})


def _posao(attio: Attio, *, osoba_id: str, tvrtka_id: str | None, naziv: str) -> None:
    postojeci = attio.trazi("deals", {"associated_people": {"target_record_id": {"$eq": osoba_id}}})
    if postojeci:
        return
    vlasnik = attio.vlasnik()
    if not vlasnik:
        logger.error("crm: vlasnik posla nije jednoznačan — posao se ne otvara za %s", osoba_id)
        return
    vrijednosti: dict[str, Any] = {
        "name": naziv, "stage": FAZA_NOVI, "owner": vlasnik,
        "associated_people": _ref("people", osoba_id),
    }
    if tvrtka_id:
        vrijednosti["associated_company"] = _ref("companies", tvrtka_id)
    attio.stvori("deals", vrijednosti)


def upisi_lead(
    attio: Attio, *, email: str, ime: str, tvrtka: str, kampanja: str, biljeska: str,
) -> str:
    """Upiši posjetitelja. Vraća id osobe. Diže GreskaAttio — pozivatelj odlučuje što s tim."""
    osoba_id, nova = _osoba(attio, email=email, ime=ime, kampanja=kampanja)
    tvrtka_id = _tvrtka(attio, tvrtka)
    if tvrtka_id and nova:
        attio.azuriraj("people", osoba_id, {"company": _ref("companies", tvrtka_id)})
    tko = " ".join((tvrtka or ime or email).split())
    _posao(attio, osoba_id=osoba_id, tvrtka_id=tvrtka_id, naziv=f"{tko} — {kampanja}")
    attio.biljeska("people", osoba_id, kampanja, biljeska)
    return osoba_id
