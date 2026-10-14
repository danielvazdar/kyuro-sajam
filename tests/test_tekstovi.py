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
    assert "1.234,50&nbsp;€" in html
    assert "Poštovani," in html


def test_podaci_racuna_su_escapeani() -> None:
    html = mail_html(ime="Ana", racuni=[RACUN])
    assert "<b>Zli</b>" not in html
    assert "&lt;b&gt;Zli&lt;/b&gt; &amp; d.o.o." in html


def test_znacka_stane_u_jedan_redak() -> None:
    # 14.10.: „u redu" se na mobitelu lomilo u dva retka — sada „OK" i bez prijeloma.
    html = mail_html(ime="", racuni=[RACUN.model_copy(update={"dobavljac": "INA"})])
    assert ">OK</span>" in html
    assert "u redu" not in html
    assert "white-space:nowrap;" in html


def test_popis_racuna_nema_stupaca() -> None:
    # 14.10.: iPhone Mail odbaci nowrap pa se uski stupac s iznosom stisne na jedno slovo.
    html = mail_html(ime="", racuni=[RACUN, RACUN])
    tablica = html[html.index("<b>&lt;b&gt;Zli"):html.index("U privitku")]
    for redak in tablica.split("<tr>")[1:]:
        assert redak.count("<td") == 1


def test_mnozina_dokumenata() -> None:
    from app.tekstovi import _dokumenata

    assert [_dokumenata(n) for n in (1, 3, 5, 11, 12, 21, 22)] == [
        "1 dokument", "3 dokumenta", "5 dokumenata", "11 dokumenata", "12 dokumenata",
        "21 dokument", "22 dokumenta",
    ]


def test_poziv_na_termin_a_ne_na_telefon() -> None:
    # Daniel 14.10.: ne želi pozive ni poruke — gumb vodi na Cal.com, popunjen imenom i adresom.
    html = mail_html(ime="Ana <Horvat>", racuni=[RACUN], email="ana@ured.hr")
    assert "tel:" not in html
    assert "https://cal.eu/kyuro/fit-call?name=Ana+%3CHorvat%3E&amp;email=ana%40ured.hr" in html
    assert "Poštovani Ana &lt;Horvat&gt;," in html


def test_mail_dobrodoslice() -> None:
    from datetime import date as datum

    from app.tekstovi import mail_dobrodoslica

    html = mail_dobrodoslica(ime="Ana <H>", poveznica="https://demo.kyuro.tech/sajam/",
                             kod="KQ7M-4RTX", istek_probe=datum(2026, 10, 23))
    assert "Poštovani Ana &lt;H&gt;," in html
    assert "23.10.2026." in html
    assert 'href="https://demo.kyuro.tech/sajam/?kod=KQ7M-4RTX"' in html
    assert "KQ7M-4RTX</b>" in html
    assert "29 € mjesečno" in html and "500 dokumenata" in html
    assert "Fakturk" not in html  # kupcu ne znači ništa
    assert "kyuro-logo.png" in html
