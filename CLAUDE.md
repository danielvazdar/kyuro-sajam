# kyuro-sajam — F1 demo za sajam (Accept, Zagreb, 16.10.2026.)

Što je: instalabilna mobilna aplikacija (PWA). Tok: **posjetitelj prvo ostavi podatke** (odmah lead u
Attiu, `/api/lead`), pa Daniel fotografira list s računima i slipovima,
Claude ih očita, aplikacija provjeri OIB i zbrojeve, složi **eURA.txt** za Synesis i pošalje
posjetitelju mail (eURA.txt + CSV + fotografija). Posjetitelj ulazi u Attio kao lead.
Živi na **https://demo.kyuro.tech/sajam/** (KVM1). Prijava u aplikaciji, ista lozinka kao demo
(apr1 hash u .env), kolačić 60 dana. nginx osnovna autentikacija za /sajam/ je isključena.

## Gdje što živi
```
app/citac.py     fotografija → računi (claude-opus-5-5, strukturirani izlaz)
app/model.py     Racun + provjere (OIB ISO 7064, zbrojevi, PDV po stopi)
app/slog.py      eURA.txt — 1:1 s kyuro-demo src/lib/slog (isti testovi položaja)
app/posta.py     Brevo mail s privitcima · app/tekstovi.py tekst maila (HR)
app/crm.py       Attio: osoba po mailu → tvrtka → posao „Lead" → bilješka
app/dnevnik.py   data/leadovi.jsonl — upisuje se PRIJE maila i Attia
web/             PWA (index.html, app.js, stil.css, sw.js, manifest)
deploy/          systemd jedinica + nginx isječak (snippets/sajam.conf)
```

## Naredbe
```
.venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest -q     provjere
node scripts/proba.mjs http://127.0.0.1:8021/                         e2e na iPhone ekranu
  (prije: ANTHROPIC_API_KEY=x BREVO_API_KEY=x ATTIO_API_KEY=x SAJAM_WEB_DIR=web
          .venv/bin/uvicorn app.main:app --port 8021)
./deploy.sh                                                           samo s čistog, gurnutog main
```

## Tvrde granice
- Brojevi se provjeravaju kodom, ne vjeruje im se iz modela. Pravila žive samo u `model.upozorenja`.
- eURA.txt je čisti ASCII, 211 znakova + CR+LF. Kodna stranica nije u Pupillinoj specifikaciji.
- Lead se upisuje u dnevnik prije slanja. Pad Attia ne smije srušiti demo pred posjetiteljem.
- Mail ne obećava „samo od sebe": uvoz u Synesis je uvijek klik čovjeka (nema API-ja).
- `/api/` se nikad ne kešira u service workeru.
- `TEST_ADRESE` (zarezom) dobivaju mail, ali ne ulaze u Attio.
