"""Mail koji knjigovođa dobije nakon što mu Daniel na sajmu pokaže aplikaciju.

Daniel je na Acceptu POSJETITELJ, ne izlagač: nema štanda. Mail zahvaljuje na razgovoru.
Raspored je tablični i sa stilovima u retku, jer Outlook i Gmail ne čitaju <style> pouzdano.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.model import Racun, upozorenja

MAIL_NASLOV = "Vaši računi sa sajma Accept, spremni za Synesis"

_TELEFON = "097 612 4852"
_TELEFON_LINK = "+385976124852"
_LOGO = "https://kyuro.tech/brand/kyuro-logo.png"  # 260×55, prikazuje se upola za oštrinu na retini

# Kyuro paleta (ista kao kyuro.tech i demo)
_TINTA = "#2a2d27"
_TINTA_2 = "#5f6459"
_PAPIR = "#f3f2ec"
_RUB = "#e9e7dd"
_GLINA = "#b0503c"
_KADULJA = "#3f7d4e"
_KADULJA_SV = "#e3f0e6"
_JANTAR = "#8a5a0a"
_JANTAR_SV = "#fbeed5"
_FONT = "Helvetica,Arial,sans-serif"


def _eur(iznos: Decimal) -> str:
    cijeli, decimale = f"{iznos:.2f}".split(".")
    s_tockama = f"{int(cijeli):,}".replace(",", ".")
    return f"{s_tockama},{decimale} €"


def _esc(tekst: str) -> str:
    return (tekst.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _znacka(cist: bool) -> str:
    boja, pozadina, tekst = (
        (_KADULJA, _KADULJA_SV, "u redu") if cist else (_JANTAR, _JANTAR_SV, "provjeriti")
    )
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'background:{pozadina};color:{boja};font-size:12px;font-weight:bold">{tekst}</span>')


def _redak(racun: Racun) -> str:
    cist = not upozorenja(racun) and not racun.nesigurno
    celija = f"padding:10px 8px;border-bottom:1px solid {_RUB};vertical-align:top"
    vrsta = "Slip" if racun.vrsta == "slip" else "Račun"
    return (
        "<tr>"
        f'<td style="{celija}"><b>{_esc(racun.dobavljac)}</b><br>'
        f'<span style="color:{_TINTA_2};font-size:12px">{vrsta} {_esc(racun.broj_racuna)}'
        f' · {racun.datum_racuna:%d.%m.%Y.}</span></td>'
        f'<td style="{celija};text-align:right;white-space:nowrap"><b>{_eur(racun.ukupno)}</b></td>'
        f'<td style="{celija};text-align:right">{_znacka(cist)}</td>'
        "</tr>"
    )


def _zaglavlje() -> str:
    return f"""<tr><td style="padding:24px 24px 18px;border-bottom:3px solid {_GLINA}">
<img src="{_LOGO}" width="130" height="28" alt="KYURO." style="display:block;border:0;
height:28px;width:130px;font:bold 24px {_FONT};color:{_TINTA}">
</td></tr>"""


def _tablica(racuni: Sequence[Racun]) -> str:
    ukupno = sum((r.ukupno for r in racuni), Decimal("0"))
    zaglavlje = (f"padding:8px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;"
                 f"color:{_TINTA_2};border-bottom:1px solid {_RUB}")
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
style="border-collapse:collapse;font-size:14px;margin:4px 0 8px">
<tr><td style="{zaglavlje};text-align:left">Dobavljač</td>
<td style="{zaglavlje};text-align:right">Iznos</td><td style="{zaglavlje}"></td></tr>
{"".join(_redak(r) for r in racuni)}
<tr><td style="padding:12px 8px"><b>Ukupno · {len(racuni)} dokumenata</b></td>
<td style="padding:12px 8px;text-align:right;white-space:nowrap"><b>{_eur(ukupno)}</b></td>
<td></td></tr></table>"""


def _privitci() -> str:
    stavka = "padding:6px 0;font-size:14px"
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
style="background:{_PAPIR};border-radius:10px;margin:20px 0">
<tr><td style="padding:16px 20px">
<div style="font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:{_TINTA_2};
margin-bottom:6px">U privitku</div>
<div style="{stavka}"><b>eURA.txt</b> · knjiga ulaznih računa za uvoz u Synesis</div>
<div style="{stavka}"><b>pregled-racuna.csv</b> · isti podaci pripremljeni za Excel</div>
<div style="{stavka}"><b>fotografija.jpg</b> · fotografija lista s računima</div>
</td></tr></table>"""


def _koraci() -> str:
    koraci = [
        "Spremite <b>eURA.txt</b> u <b>korijen diska</b>, primjerice na USB memoriju "
        "(E:\\eURA.txt). Synesis tu datoteku traži upravo ondje.",
        "U Synesisu otvorite dokument <b>e-URA</b> i kliknite <b>Učitaj iz datoteke</b>.",
        "Odaberite disk pa pregledajte račune prije spremanja.",
    ]
    retci = "".join(
        f'<tr><td style="width:28px;padding:6px 0;vertical-align:top">'
        f'<span style="display:inline-block;width:22px;height:22px;line-height:22px;'
        f'border-radius:11px;background:{_GLINA};color:#fff;text-align:center;font-size:12px;'
        f'font-weight:bold">{broj}</span></td>'
        f'<td style="padding:6px 0 6px 8px;font-size:14px">{tekst}</td></tr>'
        for broj, tekst in enumerate(koraci, start=1)
    )
    return (f'<h2 style="font-size:16px;margin:24px 0 8px;color:{_TINTA}">'
            f"Kako ih učitati u Synesis</h2>"
            f'<table role="presentation" cellpadding="0" cellspacing="0">{retci}</table>')


def _gumb() -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 24px">
<tr><td style="border-radius:10px;background:{_GLINA}">
<a href="tel:{_TELEFON_LINK}" style="display:inline-block;padding:12px 22px;color:#ffffff;
font-weight:bold;font-size:15px;text-decoration:none">Nazovite me: {_TELEFON}</a>
</td></tr></table>"""


def mail_html(*, ime: str, racuni: Sequence[Racun]) -> str:
    """`ime` stiže već escapean; podaci računa escapeaju se ovdje."""
    pozdrav = f"Poštovani {ime}," if ime else "Poštovani,"
    tijelo = f"""
<p style="margin:0 0 14px">{pozdrav}</p>
<p style="margin:0 0 18px">hvala Vam na ugodnom razgovoru danas na sajmu Accept u Zagrebu.
Kao što sam Vam pokazao na mobitelu, u privitku šaljem eURA.txt datoteku za Synesis,
složenu iz računa koje smo zajedno fotografirali:</p>
{_tablica(racuni)}
{_privitci()}
{_koraci()}
<p style="margin:16px 0 0;color:{_TINTA_2};font-size:13px">Ovo je pokazni primjer: računi
označeni s „provjeriti” zahtijevaju Vaš pregled, a datoteku je najbolje prvo učitati u
testnu kopiju knjige.</p>
<h2 style="font-size:16px;margin:28px 0 8px;color:{_TINTA}">A u Vašem uredu?</h2>
<p style="margin:0 0 14px">Tamo to može raditi bez fotografiranja: računi koji stignu
e-poštom ili kao PDF sami se očitaju, a Vi ih samo pregledate i kliknete na uvoz. Ako Vas
zanima kako bi to izgledalo kod Vas, odgovorite na ovu poruku ili me nazovite.</p>
{_gumb()}
<p style="margin:0">Lijep pozdrav,<br><b>Daniel Vazdar</b><br>
<span style="color:{_TINTA_2}">Kyuro · automatizacija knjigovodstva</span><br>
<a href="https://kyuro.tech" style="color:{_GLINA}">kyuro.tech</a></p>"""

    return f"""<!doctype html><html lang="hr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{_PAPIR}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_PAPIR}">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;
background:#ffffff;border-radius:14px;font-family:{_FONT};color:{_TINTA};font-size:15px;
line-height:1.55">
{_zaglavlje()}
<tr><td style="padding:24px 24px 28px">{tijelo}</td></tr>
</table>
<p style="max-width:560px;margin:16px auto 0;font-family:{_FONT};font-size:12px;
color:#8b9083;line-height:1.5">Ovu ste poruku primili jer ste mi na sajmu Accept ostavili
adresu. Ako ne želite da Vam se ponovno javim, samo odgovorite s „odjava”.</p>
</td></tr></table></body></html>"""
