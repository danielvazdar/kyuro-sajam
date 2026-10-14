"""Sajamski F1 demo: fotografija → računi → eURA.txt → mail posjetitelju + lead u Attio.

Iza nginxa na demo.kyuro.tech/sajam/. Prijava je u aplikaciji (`app/prijava.py`), ne u nginxu.
Javno: GET /api/zdravlje · POST /api/prijava. Sve ostalo traži kolačić prijave.
"""

from __future__ import annotations

import io
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import anthropic
from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import crm, dnevnik, posta, prijava, pristup
from app.citac import GreskaCitanja, procitaj
from app.config import Postavke
from app.model import Racun, upozorenja
from app.slog import datoteka_eura

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sajam")

MAKS_FOTOGRAFIJA_B = 15 * 1024 * 1024
MAKS_STRANICA_PX = 2400  # dovoljno za sitan tekst slipa, a zahtjev ostaje brz
MAKS_CITANJA_NA_SAT = 60  # granica troška ako lozinka ikad procuri
MAKS_RACUNA = 40
MAKS_FOTOGRAFIJA = 10  # više fotografija iz galerije; svaka se čita zasebno
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,253}\.[A-Za-z]{2,}$")
_SESIJA = re.compile(r"^[0-9a-f]{32}$")

app = FastAPI(title="Kyuro sajam", docs_url=None, redoc_url=None, openapi_url=None)


@lru_cache(maxsize=1)
def postavke() -> Postavke:
    return Postavke.iz_okoline()


@lru_cache(maxsize=1)
def klijent() -> anthropic.Anthropic:
    return anthropic.Anthropic(timeout=120.0, max_retries=2)


class _Granica:
    """Klizni prozor od sat vremena za skupe pozive. Jedan proces, pa je memorija dovoljna."""

    def __init__(self, maks: int) -> None:
        self._maks = maks
        self._vremena: deque[float] = deque()
        self._brava = threading.Lock()

    def propusti(self) -> bool:
        sada = time.monotonic()
        with self._brava:
            while self._vremena and sada - self._vremena[0] > 3600:
                self._vremena.popleft()
            if len(self._vremena) >= self._maks:
                return False
            self._vremena.append(sada)
            return True


_granica_citanja = _Granica(MAKS_CITANJA_NA_SAT)


def pripremi_fotografiju(sirovo: bytes) -> bytes:
    """Okreni po EXIF-u, smanji i spremi kao JPEG. Mobitel šalje 4000 px i krivu orijentaciju."""
    try:
        with Image.open(io.BytesIO(sirovo)) as izvorna:
            uspravna = ImageOps.exif_transpose(izvorna).convert("RGB")
        uspravna.thumbnail((MAKS_STRANICA_PX, MAKS_STRANICA_PX))
        izlaz = io.BytesIO()
        uspravna.save(izlaz, format="JPEG", quality=88)
        return izlaz.getvalue()
    except (UnidentifiedImageError, OSError) as greska:
        raise HTTPException(400, "Datoteka nije fotografija.") from greska


def _mapa_sesije(p: Postavke, sesija: str) -> Path:
    return p.data_dir / "sesije" / sesija


def u_json(racun: Racun) -> dict[str, Any]:
    return {**racun.model_dump(mode="json"), "upozorenja": upozorenja(racun)}


_brana_prijave = prijava.Brana()
ADRESA_APLIKACIJE = "https://demo.kyuro.tech/sajam/"


@lru_cache(maxsize=4)
def _spremiste(data_dir: Path) -> pristup.Spremiste:
    return pristup.Spremiste(data_dir)


@dataclass(frozen=True)
class Korisnik:
    """Daniel (lozinka) ili posjetitelj na probi (osobni kod iz maila dobrodošlice)."""

    uloga: Literal["daniel", "proba"]
    proba: pristup.Pristup | None = None


def korisnik(
    p: Annotated[Postavke, Depends(postavke)],
    token: Annotated[str | None, Cookie(alias=prijava.KOLACIC)] = None,
) -> Korisnik:
    subjekt = prijava.procitaj(token, p.tajna)
    if subjekt is None:
        raise HTTPException(401, "Prijavite se.")
    if subjekt == prijava.DANIEL:
        return Korisnik("daniel")
    kod = prijava.kod_iz_subjekta(subjekt)
    zapis = _spremiste(p.data_dir).po_kodu(kod) if kod else None
    if zapis is None or not zapis.vrijedi():
        raise HTTPException(401, "Probni rok je istekao.")
    return Korisnik("proba", zapis)


def samo_daniel(k: Annotated[Korisnik, Depends(korisnik)]) -> Korisnik:
    if k.uloga != "daniel":
        raise HTTPException(403, "Ova radnja nije dostupna na probi.")
    return k


Zasticeno = [Depends(korisnik)]


@app.get("/api/zdravlje")
def zdravlje() -> dict[str, bool]:
    return {"ok": True}


class Prijava(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lozinka: str = Field(max_length=200)


def _postavi_kolacic(odgovor: Response, vrijednost: str, trajanje_s: int) -> None:
    odgovor.set_cookie(prijava.KOLACIC, vrijednost, max_age=trajanje_s, path="/",
                       secure=True, httponly=True, samesite="strict")


@app.post("/api/prijava")
def prijavi(
    podaci: Prijava, odgovor: Response, p: Annotated[Postavke, Depends(postavke)],
) -> dict[str, bool]:
    """Danielova lozinka ILI pristupni kod posjetitelja — isto polje, ista brana."""
    if _brana_prijave.zatvorena():
        raise HTTPException(429, "Previše pokušaja. Pričekajte 15 minuta.")
    if pristup.je_kod(podaci.lozinka):
        zapis = _spremiste(p.data_dir).po_kodu(podaci.lozinka)
        if zapis is not None and zapis.vrijedi():
            istek = int(zapis.istek_dt.timestamp())
            preostalo = max(1, istek - int(time.time()))
            token = prijava.izdaj(p.tajna, subjekt=prijava.subjekt_probe(zapis.kod), istek=istek)
            _postavi_kolacic(odgovor, token, preostalo)
            return {"ok": True}
    elif prijava.lozinka_ispravna(podaci.lozinka, p.lozinka_hash):
        _postavi_kolacic(odgovor, prijava.izdaj(p.tajna), prijava.TRAJANJE_S)
        return {"ok": True}
    _brana_prijave.promasaj()
    logger.warning("prijava: kriva lozinka ili kod")
    raise HTTPException(401, "Kriva lozinka ili kod (ili je probni rok istekao).")


@app.get("/api/ja")
def ja(k: Annotated[Korisnik, Depends(korisnik)]) -> dict[str, Any]:
    if k.proba is None:
        return {"uloga": "daniel"}
    return {
        "uloga": "proba", "email": k.proba.email, "ime": k.proba.ime,
        "istek": k.proba.istek_dt.astimezone(UTC).date().isoformat(),
        "preostalo_citanja": pristup.MAKS_CITANJA - k.proba.citanja,
    }


@app.post("/api/procitaj")
def procitaj_fotografiju(
    fotografija: Annotated[UploadFile, File()],
    p: Annotated[Postavke, Depends(postavke)],
    k: Annotated[Korisnik, Depends(korisnik)],
) -> dict[str, Any]:
    sirovo = fotografija.file.read(MAKS_FOTOGRAFIJA_B + 1)
    if len(sirovo) > MAKS_FOTOGRAFIJA_B:
        raise HTTPException(413, "Fotografija je prevelika.")
    if not _granica_citanja.propusti():
        raise HTTPException(429, "Dosegnuta je satna granica čitanja.")
    jpeg = pripremi_fotografiju(sirovo)
    if k.proba is not None and not _spremiste(p.data_dir).zabiljezi_citanje(k.proba.kod):
        raise HTTPException(
            429, f"Iskorišteno je svih {pristup.MAKS_CITANJA} čitanja probnog roka.",
        )

    sesija = uuid.uuid4().hex
    mapa = _mapa_sesije(p, sesija)
    mapa.mkdir(parents=True, mode=0o700)
    (mapa / "fotografija.jpg").write_bytes(jpeg)

    pocetak = time.monotonic()
    try:
        racuni = procitaj(jpeg, "image/jpeg", klijent())
    except GreskaCitanja as greska:
        raise HTTPException(502, str(greska)) from greska
    logger.info("procitaj: sesija %s, %d računa, %.1f s", sesija, len(racuni),
                time.monotonic() - pocetak)
    return {"sesija": sesija, "racuni": [u_json(r) for r in racuni]}


class Popis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    racuni: list[Racun] = Field(min_length=1, max_length=MAKS_RACUNA)


@app.post("/api/provjeri", dependencies=Zasticeno)
def provjeri(popis: Popis) -> dict[str, Any]:
    """Ponovna provjera nakon ručne izmjene na ekranu — pravila žive samo ovdje."""
    return {"racuni": [u_json(r) for r in popis.racuni]}


@app.post("/api/eura", response_class=PlainTextResponse, dependencies=Zasticeno)
def eura(popis: Popis) -> str:
    return datoteka_eura(popis.racuni)


class Posjetitelj(BaseModel):
    """Tko je posjetitelj. Upisuje se PRVI, prije demonstracije (Daniel, 14.10.)."""

    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    ime: str = Field(default="", max_length=80)
    tvrtka: str = Field(default="", max_length=120)
    privola: bool

    @field_validator("email")
    @classmethod
    def _email(cls, vrijednost: str) -> str:
        vrijednost = vrijednost.strip().lower()
        if not _EMAIL.match(vrijednost):
            raise ValueError("neispravna adresa")
        return vrijednost


class Slanje(Posjetitelj):
    racuni: list[Racun] = Field(min_length=1, max_length=MAKS_RACUNA)
    sesije: list[str] = Field(default_factory=list, max_length=MAKS_FOTOGRAFIJA)

    @field_validator("sesije")
    @classmethod
    def _sesije(cls, vrijednosti: list[str]) -> list[str]:
        if any(not _SESIJA.match(v) for v in vrijednosti):
            raise ValueError("neispravna sesija")
        return list(dict.fromkeys(vrijednosti))  # bez duplikata, redoslijed ostaje


def _biljeska_lead(posjetitelj: Posjetitelj) -> str:
    return "\n".join([
        "Upoznali smo se na sajmu Accept; ostavio/la je podatke prije F1 demonstracije.",
        f"Tvrtka: {posjetitelj.tvrtka or '—'}",
    ])


def _biljeska_slanje(slanje: Slanje) -> str:
    retci = [f"{r.dobavljac} · {r.broj_racuna} · {r.ukupno:.2f} EUR" for r in slanje.racuni]
    return "\n".join([
        "F1 demo: skenirali smo njihove račune i poslali eURA.txt na mail.",
        f"Računa: {len(slanje.racuni)}",
        *retci,
    ])


@app.post("/api/lead", dependencies=[Depends(samo_daniel)])
def lead(posjetitelj: Posjetitelj, p: Annotated[Postavke, Depends(postavke)]) -> dict[str, Any]:
    """Prvi korak: posjetitelj ostavi podatke i odmah postaje lead, prije ikakve demonstracije."""
    if not posjetitelj.privola:
        raise HTTPException(400, "Bez privole ne možemo nastaviti.")
    test = posjetitelj.email in p.test_adrese
    dnevnik.upisi(p.data_dir, {
        "dogadaj": "lead", "email": posjetitelj.email, "ime": posjetitelj.ime,
        "tvrtka": posjetitelj.tvrtka, "test": test,
    })
    attio_ok = test or _u_attio(posjetitelj, p, _biljeska_lead(posjetitelj))
    return {"ok": True, "attio": attio_ok, "dobrodoslica": _dobrodoslica(posjetitelj, p)}


def _dobrodoslica(posjetitelj: Posjetitelj, p: Postavke) -> bool:
    """Osobni probni kod + mail dobrodošlice. Pad maila ne zaustavlja demo pred posjetiteljem."""
    zapis = _spremiste(p.data_dir).izdaj(email=posjetitelj.email, ime=posjetitelj.ime)
    poruka = posta.sastavi_dobrodoslicu(
        p, primatelj=posjetitelj.email, ime=posjetitelj.ime, poveznica=ADRESA_APLIKACIJE,
        kod=zapis.za_prikaz, istek_probe=zapis.istek_dt.date(),
    )
    try:
        poruka_id = posta.posalji(p, poruka)
    except posta.GreskaSlanja:
        dnevnik.upisi(p.data_dir, {"dogadaj": "dobrodoslica_pala", "email": posjetitelj.email})
        return False
    dnevnik.upisi(p.data_dir, {"dogadaj": "dobrodoslica", "email": posjetitelj.email,
                               "istek_probe": zapis.istek, "brevo_id": poruka_id})
    return True


@app.post("/api/posalji")
def posalji(
    slanje: Slanje, p: Annotated[Postavke, Depends(postavke)],
    k: Annotated[Korisnik, Depends(korisnik)],
) -> dict[str, Any]:
    if k.proba is not None:
        # Na probi mail ide UVIJEK na adresu iz probe — tijelo zahtjeva ne može ga preusmjeriti.
        slanje = slanje.model_copy(update={"email": k.proba.email, "ime": k.proba.ime})
    if not slanje.privola:
        raise HTTPException(400, "Bez privole ne šaljemo.")
    test = slanje.email in p.test_adrese
    dnevnik.upisi(p.data_dir, {
        "dogadaj": "slanje", "email": slanje.email, "racuna": len(slanje.racuni),
        "sesije": slanje.sesije, "test": test,
    })

    putanje = (_mapa_sesije(p, sesija) / "fotografija.jpg" for sesija in slanje.sesije)
    fotografije = [putanja.read_bytes() for putanja in putanje if putanja.exists()]

    poruka = posta.sastavi(p, primatelj=slanje.email, ime=slanje.ime, racuni=slanje.racuni,
                           eura=datoteka_eura(slanje.racuni), fotografije=fotografije,
                           samostalno=k.proba is not None)
    try:
        poruka_id = posta.posalji(p, poruka)
    except posta.GreskaSlanja as greska:
        dnevnik.upisi(p.data_dir, {"dogadaj": "mail_pao", "email": slanje.email})
        raise HTTPException(502, str(greska)) from greska
    dnevnik.upisi(p.data_dir, {"dogadaj": "mail_poslan", "email": slanje.email,
                               "brevo_id": poruka_id})

    biljeska = _biljeska_slanje(slanje)
    if k.proba is not None:
        biljeska = "SAM koristi probu (dobar znak za nastavak).\n" + biljeska
    attio_ok = test or _u_attio(slanje, p, biljeska)
    return {"poslano": True, "attio": attio_ok}


def _u_attio(posjetitelj: Posjetitelj, p: Postavke, biljeska: str) -> bool:
    """Attio ne smije srušiti demo: lead je već u dnevniku i može se dopuniti kasnije.

    Upis je idempotentan po mailu: druga bilješka ide na istu osobu i isti posao.
    """
    try:
        osoba_id = crm.upisi_lead(
            crm.Attio(p.attio_api_key), email=posjetitelj.email, ime=posjetitelj.ime,
            tvrtka=posjetitelj.tvrtka, kampanja=p.kampanja, biljeska=biljeska,
        )
    except crm.GreskaAttio as greska:
        logger.error("attio: %s", greska)
        dnevnik.upisi(p.data_dir, {"dogadaj": "attio_pao", "email": posjetitelj.email})
        return False
    dnevnik.upisi(p.data_dir, {"dogadaj": "attio_upisan", "email": posjetitelj.email,
                               "osoba": osoba_id})
    return True


# Samo za lokalni razvoj i e2e probu: u produkciji web/ poslužuje nginx.
if os.getenv("SAJAM_WEB_DIR"):
    app.mount("/", StaticFiles(directory=os.environ["SAJAM_WEB_DIR"], html=True), name="web")
