import io
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from passlib.hash import apr_md5_crypt
from PIL import Image

from app import crm, dnevnik, main, posta, prijava
from app.model import Racun

RACUN = Racun(
    dobavljac="INA d.d.", oib_dobavljaca="10493141768", broj_racuna="4471/1/2",
    datum_racuna=date(2026, 8, 4), ukupno=Decimal("64.50"),
    osnovica25=Decimal("51.60"), pdv25=Decimal("12.90"),
)


LOZINKA_HASH = apr_md5_crypt.hash("ispravna")


@pytest.fixture
def klijent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for kljuc in ("ANTHROPIC_API_KEY", "BREVO_API_KEY", "ATTIO_API_KEY"):
        monkeypatch.setenv(kljuc, "test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TEST_ADRESE", "daniel@test.hr")
    monkeypatch.setenv("SAJAM_LOZINKA_HASH", LOZINKA_HASH)
    monkeypatch.setenv("SAJAM_TAJNA", "tajna-za-test")
    monkeypatch.setattr(main, "_brana_prijave", prijava.Brana())
    main.postavke.cache_clear()
    klijent = TestClient(main.app, base_url="https://testserver")
    assert klijent.post("/api/prijava", json={"lozinka": "ispravna"}).status_code == 200
    yield klijent
    main.postavke.cache_clear()


def _jpeg() -> bytes:
    izlaz = io.BytesIO()
    Image.new("RGB", (3000, 2000), "white").save(izlaz, format="JPEG")
    return izlaz.getvalue()


def _slanje(**izmjene: Any) -> dict[str, Any]:
    return {"racuni": [RACUN.model_dump(mode="json")], "email": "Ana@Ured.hr",
            "ime": "Ana", "tvrtka": "Ured d.o.o.", "privola": True, **izmjene}


def test_procitaj_vraca_racune_i_upozorenja(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    primljeno: dict[str, bytes] = {}

    def lazni_citac(slika: bytes, media_type: str, _klijent: object) -> list[Racun]:
        primljeno["slika"] = slika
        return [RACUN, RACUN.model_copy(update={"oib_dobavljaca": "1"})]

    monkeypatch.setattr(main, "procitaj", lazni_citac)
    odgovor = klijent.post("/api/procitaj", files={"fotografija": ("a.jpg", _jpeg(), "image/jpeg")})
    assert odgovor.status_code == 200
    tijelo = odgovor.json()
    assert len(tijelo["racuni"]) == 2
    assert tijelo["racuni"][0]["upozorenja"] == []
    assert tijelo["racuni"][1]["upozorenja"]
    with Image.open(io.BytesIO(primljeno["slika"])) as slika:
        assert max(slika.size) == main.MAKS_STRANICA_PX
    assert (tmp_path / "sesije" / tijelo["sesija"] / "fotografija.jpg").exists()


def test_procitaj_odbija_ne_sliku(klijent: TestClient) -> None:
    odgovor = klijent.post("/api/procitaj", files={"fotografija": ("a.jpg", b"nije", "image/jpeg")})
    assert odgovor.status_code == 400


def test_eura_daje_datoteku(klijent: TestClient) -> None:
    odgovor = klijent.post("/api/eura", json={"racuni": [RACUN.model_dump(mode="json")]})
    assert odgovor.status_code == 200
    assert odgovor.text.startswith("10493141768")
    assert odgovor.text.endswith("\r\n")


def test_posalji_salje_mail_i_upisuje_lead(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    poslano: list[dict[str, Any]] = []
    leadovi: list[dict[str, Any]] = []
    monkeypatch.setattr(posta, "posalji", lambda _p, poruka: poslano.append(poruka) or "id-1")
    monkeypatch.setattr(crm, "upisi_lead", lambda _a, **kw: leadovi.append(kw) or "osoba-1")

    odgovor = klijent.post("/api/posalji", json=_slanje())
    assert odgovor.json() == {"poslano": True, "attio": True}
    assert poslano[0]["to"] == [{"email": "ana@ured.hr", "name": "Ana"}]
    imena = [p["name"] for p in poslano[0]["attachment"]]
    assert imena == ["eURA.txt", "pregled-racuna.csv"]
    assert leadovi[0]["tvrtka"] == "Ured d.o.o."
    dogadaji = [z["dogadaj"] for z in dnevnik.procitaj_sve(tmp_path)]
    assert dogadaji == ["lead", "mail_poslan", "attio_upisan"]


def test_pad_attia_ne_rusi_slanje(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(posta, "posalji", lambda _p, _poruka: "id-1")

    def pada(_a: object, **_kw: object) -> str:
        raise crm.GreskaAttio("503")

    monkeypatch.setattr(crm, "upisi_lead", pada)
    odgovor = klijent.post("/api/posalji", json=_slanje())
    assert odgovor.json() == {"poslano": True, "attio": False}
    assert dnevnik.procitaj_sve(tmp_path)[-1]["dogadaj"] == "attio_pao"


def test_pad_maila_vraca_gresku_ali_lead_ostaje(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    def pada(_p: object, _poruka: object) -> str:
        raise posta.GreskaSlanja("Mail nije poslan.")

    monkeypatch.setattr(posta, "posalji", pada)
    odgovor = klijent.post("/api/posalji", json=_slanje())
    assert odgovor.status_code == 502
    assert [z["dogadaj"] for z in dnevnik.procitaj_sve(tmp_path)] == ["lead", "mail_pao"]


def test_test_adresa_ne_ide_u_attio(klijent: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(posta, "posalji", lambda _p, _poruka: "id-1")

    def ne_smije(_a: object, **_kw: object) -> str:
        raise AssertionError("test adresa ušla u Attio")

    monkeypatch.setattr(crm, "upisi_lead", ne_smije)
    assert klijent.post("/api/posalji", json=_slanje(email="daniel@test.hr")).status_code == 200


@pytest.mark.parametrize("izmjena", [
    {"privola": False},
    {"email": "nije-adresa"},
    {"racuni": []},
    {"sesije": ["../../etc"]},
])
def test_neispravno_slanje_se_odbija(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, izmjena: dict[str, Any],
) -> None:
    monkeypatch.setattr(posta, "posalji", lambda _p, _poruka: pytest.fail("poslano"))
    assert klijent.post("/api/posalji", json=_slanje(**izmjena)).status_code in (400, 422)


def test_bez_prijave_api_je_zatvoren(klijent: TestClient) -> None:
    klijent.cookies.clear()
    for putanja in ("/api/eura", "/api/provjeri", "/api/posalji"):
        assert klijent.post(putanja, json={}).status_code == 401
    assert klijent.get("/api/ja").status_code == 401
    assert klijent.get("/api/zdravlje").status_code == 200


def test_kriva_lozinka_i_brana(klijent: TestClient) -> None:
    klijent.cookies.clear()
    for _ in range(10):
        assert klijent.post("/api/prijava", json={"lozinka": "kriva"}).status_code == 401
    assert klijent.post("/api/prijava", json={"lozinka": "ispravna"}).status_code == 429


def test_prijava_daje_trajni_sigurni_kolacic(klijent: TestClient) -> None:
    klijent.cookies.clear()
    odgovor = klijent.post("/api/prijava", json={"lozinka": "ispravna"})
    kolacic = odgovor.headers["set-cookie"].lower()
    assert "httponly" in kolacic and "secure" in kolacic and "samesite=strict" in kolacic
    assert f"max-age={prijava.TRAJANJE_S}" in kolacic
    assert klijent.get("/api/ja").status_code == 200


def test_token_istekne_i_ne_da_se_krivotvoriti() -> None:
    token = prijava.izdaj("tajna", sada=1000)
    assert prijava.vrijedi(token, "tajna", sada=2000)
    assert not prijava.vrijedi(token, "tajna", sada=1000 + prijava.TRAJANJE_S + 1)
    assert not prijava.vrijedi(token, "druga-tajna", sada=2000)
    istek, potpis = token.split(".")
    assert not prijava.vrijedi(f"{int(istek) + 999}.{potpis}", "tajna", sada=2000)


def test_vise_fotografija_ide_u_privitak(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    sesije = []
    for _ in range(2):
        monkeypatch.setattr(main, "procitaj", lambda *_a: [RACUN])
        odgovor = klijent.post("/api/procitaj",
                               files={"fotografija": ("a.jpg", _jpeg(), "image/jpeg")})
        sesije.append(odgovor.json()["sesija"])
    poslano: list[dict[str, Any]] = []
    monkeypatch.setattr(posta, "posalji", lambda _p, poruka: poslano.append(poruka) or "id")
    monkeypatch.setattr(crm, "upisi_lead", lambda _a, **_kw: "osoba")
    klijent.post("/api/posalji", json=_slanje(sesije=[*sesije, sesije[0]]))
    imena = [p["name"] for p in poslano[0]["attachment"]]
    assert imena == ["eURA.txt", "pregled-racuna.csv", "fotografija-1.jpg", "fotografija-2.jpg"]
    assert "fotografija-1 … 2.jpg" in str(poslano[0]["htmlContent"])
