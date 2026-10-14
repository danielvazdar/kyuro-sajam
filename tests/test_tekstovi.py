from datetime import date
from decimal import Decimal

from app.model import Racun
from app.tekstovi import mail_html

RACUN = Racun(
    dobavljac="<b>Zli</b> & d.o.o.", oib_dobavljaca="10493141768", broj_racuna="1/1/1",
    datum_racuna=date(2026, 10, 2), ukupno=Decimal("1234.50"),
    osnovica25=Decimal("987.60"), pdv25=Decimal("246.90"),
)


def test_daniel_je_posjetitelj_a_ne_izlagac() -> None:
    # Regresija 14.10.: mail je zahvaljivao na posjetu „našem štandu", a Kyuro nema štand.
    html = mail_html(ime="Ana", racuni=[RACUN]).lower()
    assert "štand" not in html
    assert "razgovoru" in html


def test_zaglavlje_s_logom_i_iznosi_hr() -> None:
    html = mail_html(ime="", racuni=[RACUN])
    assert "kyuro-logo.png" in html
    assert "1.234,50 €" in html
    assert "Poštovani," in html


def test_podaci_racuna_su_escapeani() -> None:
    html = mail_html(ime="Ana", racuni=[RACUN])
    assert "<b>Zli</b>" not in html
    assert "&lt;b&gt;Zli&lt;/b&gt; &amp; d.o.o." in html
