#!/usr/bin/env bash
# Deploy sajamskog demoa na KVM1 → https://demo.kyuro.tech/sajam/
# Šalje točno ono što je na GitHub main (mora biti čisto i gurnuto), nakon lokalnih provjera.
set -euo pipefail

VPS="daniel@187.124.167.214"
APP_DIR="/home/daniel/kyuro-sajam"
WEB_DIR="/var/www/sajam"
KORIJEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KORIJEN"

echo "→ vrata izdanja: grana main, čisto, jednako origin/main"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "✗ nisi na main" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "✗ ima nespremljenih izmjena" >&2; exit 1; }
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "✗ main nije jednak origin/main" >&2; exit 1; }

echo "→ provjere (ruff + mypy + pytest)"
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -q

echo "→ backend"
rsync -az --delete --exclude '__pycache__' app requirements.txt "${VPS}:${APP_DIR}/"
ssh "$VPS" "cd ${APP_DIR} && [ -d .venv ] || python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt && mkdir -p -m 700 data && sudo systemctl restart kyuro-sajam"

echo "→ web"
rsync -az --delete --chmod=D755,F644 web/ "${VPS}:${WEB_DIR}/"

echo "→ provjera na odredištu"
# Uvicorn treba nekoliko sekundi nakon restarta; jedan pokušaj odmah bi lažno pao.
ssh "$VPS" 'for i in $(seq 1 15); do curl -sf http://127.0.0.1:8020/api/zdravlje >/dev/null && exit 0; sleep 1; done; exit 1' \
  || { echo "✗ servis ne odgovara nakon restarta" >&2; exit 1; }
echo "✓ servis odgovara"
# Prijava je u aplikaciji (app/prijava.py). Bez kolačića svaka API ruta osim zdravlja mora vratiti 401.
ZDRAVLJE="$(curl -s -o /dev/null -w '%{http_code}' https://demo.kyuro.tech/sajam/api/zdravlje || echo 000)"
JA="$(curl -s -o /dev/null -w '%{http_code}' https://demo.kyuro.tech/sajam/api/ja || echo 000)"
CITAJ="$(curl -s -o /dev/null -w '%{http_code}' -X POST https://demo.kyuro.tech/sajam/api/procitaj || echo 000)"
[ "$ZDRAVLJE" = "200" ] && echo "✓ /sajam/ je gore" || { echo "✗ zdravlje vraća $ZDRAVLJE" >&2; exit 1; }
[ "$JA" = "401" ] && [ "$CITAJ" = "401" ] && echo "✓ API je zaključan bez prijave" \
  || { echo "✗ API bez prijave vraća $JA / $CITAJ (očekivano 401)" >&2; exit 1; }
echo "✓ gotovo: https://demo.kyuro.tech/sajam/"
