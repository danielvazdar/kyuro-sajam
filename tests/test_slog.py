"""Isti položaji polja kao `kyuro-demo` eura.test.ts — dva emitera, jedna specifikacija."""

from datetime import date
from decimal import Decimal

from app.model import Racun
from app.slog import SIRINA_RETKA_EURA, datoteka_eura, redak_eura, u_ascii

OSNOVA = Racun(
    dobavljac="INA d.d.",
    oib_dobavljaca="10493141768",
    broj_racuna="4471/1/2",
    datum_racuna=date(2026, 8, 4),
    datum_dospijeca=date(2026, 8, 19),
    ukupno=Decimal("64.50"),
    osnovica25=Decimal("51.60"),
    pdv25=Decimal("12.90"),
    napomena="Gorivo",
)


def test_redak_ima_tocnu_sirinu() -> None:
    assert len(redak_eura(OSNOVA)) == SIRINA_RETKA_EURA


def test_polja_su_na_polozajima_iz_specifikacije() -> None:
    redak = redak_eura(OSNOVA)
    assert redak[0:11] == "10493141768"
    assert redak[11:18] == " " * 7
    assert redak[18:33] == "4471/1/2       "
    assert redak[33:41] == "04082026"
    assert redak[41:49] == "19082026"
    assert redak[49:63] == "         64.50"
    assert redak[63:77] == "          0.00"
    assert redak[147:161] == "         12.90"


def test_nula_je_0_00() -> None:
    redak = redak_eura(OSNOVA.model_copy(update={"ukupno": Decimal("0")}))
    assert redak[49:63] == "          0.00"


def test_dijakritike_i_duge_crtice_u_ascii() -> None:
    redak = redak_eura(OSNOVA.model_copy(update={"napomena": "Račun za gorivo — čšžđ"}))
    assert len(redak.encode("utf-8")) == SIRINA_RETKA_EURA
    assert "Racun za gorivo - cszd" in redak


def test_predugacko_se_reze() -> None:
    redak = redak_eura(OSNOVA.model_copy(update={
        "napomena": "x" * 80, "broj_racuna": "1234567890123456789",
    }))
    assert redak[161:211] == "x" * 50
    assert redak[18:33] == "123456789012345"


def test_bez_dospijeca_koristi_datum_racuna() -> None:
    redak = redak_eura(OSNOVA.model_copy(update={"datum_dospijeca": None}))
    assert redak[41:49] == "04082026"


def test_bez_napomene_ide_naziv_dobavljaca() -> None:
    redak = redak_eura(OSNOVA.model_copy(update={"napomena": ""}))
    assert redak[161:211].rstrip() == "INA d.d."


def test_datoteka_crlf_i_cisti_ascii() -> None:
    sadrzaj = datoteka_eura([OSNOVA, OSNOVA])
    assert len(sadrzaj) == (SIRINA_RETKA_EURA + 2) * 2
    assert sadrzaj.endswith("\r\n")
    assert all(0x20 <= ord(z) <= 0x7E or z in "\r\n" for z in sadrzaj)


def test_prazan_popis_prazna_datoteka() -> None:
    assert datoteka_eura([]) == ""


def test_u_ascii_izbacuje_sve_izvan_ascii() -> None:
    assert u_ascii("Đuro „Ćiro” € 5") == 'Duro "Ciro"  5'
