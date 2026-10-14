"""Tekst maila posjetitelju. Hrvatski, za knjigovođe — nacrt, dorada kroz `peer gpt`."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.model import Racun, upozorenja

MAIL_NASLOV = "Vaši računi sa sajma, spremni za Synesis"

_TELEFON = "097 612 4852"
_TELEFON_LINK = "+385976124852"


def _eur(iznos: Decimal) -> str:
    cijeli, decimale = f"{iznos:.2f}".split(".")
    s_tockama = f"{int(cijeli):,}".replace(",", ".")
    return f"{s_tockama},{decimale} €"


def _redak(racun: Racun) -> str:
    oznaka = (
        '<span style="color:#b45309">provjeriti</span>' if upozorenja(racun) or racun.nesigurno
        else '<span style="color:#15803d">u redu</span>'
    )
    celija = 'style="padding:6px 8px;border-bottom:1px solid #e5e7eb'
    return (
        "<tr>"
        f'<td {celija}">{_esc(racun.dobavljac)}</td>'
        f'<td {celija}">{_esc(racun.broj_racuna)}</td>'
        f'<td {celija};text-align:right">{_eur(racun.ukupno)}</td>'
        f'<td {celija}">{oznaka}</td>'
        "</tr>"
    )


def _esc(tekst: str) -> str:
    return (tekst.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def mail_html(*, ime: str, racuni: Sequence[Racun]) -> str:
    """`ime` stiže već escapean; podaci računa escapeaju se ovdje."""
    pozdrav = f"Poštovani {ime}," if ime else "Poštovani,"
    retci = "".join(_redak(r) for r in racuni)
    ukupno = sum((r.ukupno for r in racuni), Decimal("0"))
    return f"""<!doctype html><html lang="hr"><body style="margin:0;background:#f6f7f9">
<div style="max-width:600px;margin:0 auto;padding:24px;font-family:Arial,Helvetica,sans-serif;
color:#111827;font-size:15px;line-height:1.55;background:#ffffff">
<p>{pozdrav}</p>
<p>hvala što ste svratili na naš štand. U privitku su računi koje smo zajedno skenirali:</p>
<table style="border-collapse:collapse;width:100%;font-size:14px;margin:12px 0">
<thead><tr style="background:#f3f4f6;text-align:left">
<th style="padding:6px 8px">Dobavljač</th><th style="padding:6px 8px">Broj</th>
<th style="padding:6px 8px;text-align:right">Iznos</th><th style="padding:6px 8px">Stanje</th>
</tr></thead><tbody>{retci}</tbody>
<tfoot><tr><td colspan="2" style="padding:6px 8px"><b>Ukupno ({len(racuni)})</b></td>
<td style="padding:6px 8px;text-align:right"><b>{_eur(ukupno)}</b></td><td></td></tr></tfoot>
</table>
<p><b>U privitku su tri datoteke:</b></p>
<ul style="padding-left:20px">
<li><b>eURA.txt</b>: knjiga ulaznih računa u obliku koji Synesis učitava</li>
<li><b>pregled-racuna.csv</b>: isti podaci za Excel</li>
<li><b>fotografija.jpg</b>: snimka lista s računima</li>
</ul>
<p><b>Kako ih učitati u Synesis:</b></p>
<ol style="padding-left:20px">
<li>Spremite eURA.txt u <b>korijen diska</b>, na primjer na USB stick (E:\\eURA.txt).
Synesis datoteku traži samo tamo.</li>
<li>U Synesisu otvorite dokument <b>e-URA</b> i kliknite <b>Učitaj iz datoteke</b>.</li>
<li>Odaberite disk i pregledajte račune prije spremanja.</li>
</ol>
<p style="color:#6b7280;font-size:13px">Ovo je demonstracija: računi označeni s „provjeriti”
zahtijevaju Vaš pregled, a datoteku je najbolje prvo učitati u testnu kopiju knjige.</p>
<p>U Vašem uredu ovo radi bez fotografiranja: računi koji stignu mailom ili kao PDF
pročitaju se sami, a Vi samo pregledate i kliknete uvoz. Ako Vas zanima kako bi to
izgledalo kod Vas, javite se na ovaj mail ili na
<a href="tel:{_TELEFON_LINK}">{_TELEFON}</a>.</p>
<p>Lijep pozdrav,<br>Daniel Vazdar<br>Kyuro · <a href="https://kyuro.tech">kyuro.tech</a></p>
<p style="color:#9ca3af;font-size:12px">Ovaj mail ste dobili jer ste na sajmu ostavili
adresu. Ako ne želite da Vam se ponovno javimo, samo odgovorite s „odjava”.</p>
</div></body></html>"""
