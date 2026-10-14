from datetime import date
from decimal import Decimal

from app.citac import u_racun
from app.model import Racun, oib_je_ispravan, upozorenja

CIST = Racun(
    dobavljac="INA d.d.",
    oib_dobavljaca="10493141768",
    broj_racuna="4471/1/2",
    datum_racuna=date(2026, 8, 4),
    ukupno=Decimal("64.50"),
    osnovica25=Decimal("51.60"),
    pdv25=Decimal("12.90"),
)


def test_oib() -> None:
    assert oib_je_ispravan("10493141768")
    assert not oib_je_ispravan("10493141769")
    assert not oib_je_ispravan("1049314176")
    assert not oib_je_ispravan("")


def test_cist_racun_nema_upozorenja() -> None:
    assert upozorenja(CIST) == []


def test_zbroj_koji_se_ne_slaze() -> None:
    nalazi = upozorenja(CIST.model_copy(update={"ukupno": Decimal("70.00")}))
    assert any("ukupni iznos" in n for n in nalazi)


def test_razlika_od_centa_je_zaokruzivanje() -> None:
    assert upozorenja(CIST.model_copy(update={"ukupno": Decimal("64.51")})) == []


def test_pdv_ne_odgovara_osnovici() -> None:
    nalazi = upozorenja(CIST.model_copy(update={
        "pdv25": Decimal("10.00"), "ukupno": Decimal("61.60"),
    }))
    assert nalazi == ["PDV 25 % ne odgovara osnovici"]


def test_krivi_oib_i_prazan_broj() -> None:
    izmjena = {"oib_dobavljaca": "12345678901", "broj_racuna": ""}
    nalazi = upozorenja(CIST.model_copy(update=izmjena))
    assert len(nalazi) == 2


def test_oib_zadrzava_samo_znamenke() -> None:
    assert Racun(oib_dobavljaca="HR 104-931", datum_racuna=date(2026, 1, 1)).oib_dobavljaca == (
        "104931"
    )


def test_u_racun_iz_sirovog_izlaza_modela() -> None:
    racun = u_racun({
        "vrsta": "slip", "dobavljac": "Konzum", "oib_dobavljaca": "10493141768",
        "broj_racuna": "12/PJ1/3", "datum_racuna": "2026-10-01", "datum_dospijeca": "",
        "ukupno": "12,50 €", "osnovica25": "10.00", "pdv25": "2.50", "nesigurno": ["broj_racuna"],
    })
    assert racun is not None
    assert racun.vrsta == "slip"
    assert racun.ukupno == Decimal("12.50")
    assert racun.datum_dospijeca is None
    assert racun.nesigurno == ("broj_racuna",)


def test_u_racun_neocitljiv_datum_je_oznacen() -> None:
    racun = u_racun({"datum_racuna": "nečitljivo", "ukupno": "abc"})
    assert racun is not None
    assert "datum_racuna" in racun.nesigurno
    assert racun.ukupno == Decimal("0.00")
