import io
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import crm, dnevnik, main, posta
from app.model import Racun

RACUN = Racun(
    dobavljac="INA d.d.", oib_dobavljaca="10493141768", broj_racuna="4471/1/2",
    datum_racuna=date(2026, 8, 4), ukupno=Decimal("64.50"),
    osnovica25=Decimal("51.60"), pdv25=Decimal("12.90"),
)


@pytest.fixture
def klijent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for kljuc in ("ANTHROPIC_API_KEY", "BREVO_API_KEY", "ATTIO_API_KEY"):
        monkeypatch.setenv(kljuc, "test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TEST_ADRESE", "daniel@test.hr")
    main.postavke.cache_clear()
    yield TestClient(main.app)
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
    {"sesija": "../../etc"},
])
def test_neispravno_slanje_se_odbija(
    klijent: TestClient, monkeypatch: pytest.MonkeyPatch, izmjena: dict[str, Any],
) -> None:
    monkeypatch.setattr(posta, "posalji", lambda _p, _poruka: pytest.fail("poslano"))
    assert klijent.post("/api/posalji", json=_slanje(**izmjena)).status_code in (400, 422)
