# DECISIONS

## 2026-10-14 — sajamski demo kao zaseban servis
- Zaseban repo, ne modul u kyuro-demo: demo je statičan bez mreže (tvrda granica), ovo mora čitati, slati i pisati u CRM.
- Putanja `demo.kyuro.tech/sajam/` umjesto nove poddomene: ista lozinka, postojeći certifikat, bez DNS izmjene dva dana prije sajma.
- Jedna fotografija cijelog lista (Daniel). Čitač: `claude-opus-5-5`, effort medium, `fallbacks: "default"`. Trošak ~1–3 centa po listu (Daniel odobrio).
- eURA emiter prenesen u Python 1:1 iz kyuro-demo; testovi drže iste položaje polja.
- Attio: posao „<tvrtka> — Accept sajam 2026" u fazi Lead, vrijednost prazna; postojeća osoba se ne prepisuje.
- PWA (Daniel): ljuska radi offline; mail bez mreže čeka u lokalnom redu i šalje se kad se veza vrati.
- Ključevi na KVM1 (`/home/daniel/kyuro-sajam/.env`) kopirani iz webinar-funnela uz Danielov pristanak (14.10.), samo za sajam. Poslije sajma: vlastiti ključevi (issue).

## 2026-10-14 — prijava u aplikaciji umjesto nginx basic auth
- Na iPhoneu je aplikacija s početnog zaslona čekala 10–15 s na okvir lozinke i nije pamtila prijavu.
- Sada: ista lozinka kao demo (apr1 hash kopiran u .env), HttpOnly/Secure/SameSite=Strict kolačić 60 dana, 10 krivih pokušaja / 15 min.
- Ljuska je javna i otvara se iz service workera (spremnik prvi); API bez prijave vraća 401.
- 2026-10-14: čitač effort medium → low (6–7 s umjesto 9–11 s po listu, ista točnost na probnom listu).

## 2026-10-14 — podaci posjetitelja PRVI, ne zadnji
- Daniel: lead prije demonstracije. `/api/lead` upisuje dnevnik + Attio odmah; slanje na kraju je jedan dodir.
- „Novi posjetitelj, isti računi”: novi lead, bez ponovnog čitanja istog lista.
