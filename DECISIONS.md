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

## 2026-10-14 — licenca i položaj aplikacije
- Daniel: ova mala samostalna app ostaje **njegova i licencira se** (ne instalira se kod klijenta). Pravilo „alat živi kod klijenta" vrijedi za veće sustave po mjeri.
- Tržište je malo: od 1.1.2026 domaći R1 stižu kao eRačun (Synesis ih knjiži besplatno). Ostaju slipovi (trajno izuzeti) i strani računi → tako se i prodaje. App je ulaz u veliki demo (demo.kyuro.tech, PWA na tabletu).
- Cijena nije odlučena → issue #3.

## 2026-10-14 — cijena i isporuka (Daniel)
- **29 €/mj po uredu, do 500 dokumenata** (+10 € za svakih dodatnih 500). **Probni rok 7 dana** besplatno.
- Naplata **računom iz Fakturka** (virman), bez kartičnog plaćanja zasad.
- Isporuka: PWA s poveznice + login po uredu, **bez trgovina aplikacija**. Daniel je hosta i licencira.
- Prije prvog kupca: računi po uredu (multi-tenant), brojač dokumenata, brisanje fotografija nakon 30 dana, DPA.
- Odbačeno: 1.000 € + 50 €/mj (prevelik ulaz za tako malu app), 49 €/mj, 30-dnevni probni rok.

## 2026-10-14 — svaki posjetitelj dobiva dobrodošlicu i 7 dana probe (Daniel)
- Nakon podataka posjetitelja: 3 ekrana dobrodošlice, automatski mail dobrodošlice s **osobnim pristupnim kodom** (KQ7M-4RTX) i gumbom koji prijavljuje (?kod=).
- Kod, a ne samo poveznica: iPhone aplikacija s početnog zaslona ne dijeli kolačiće sa Safarijem.
- Na probi: bez ekrana podataka, mail uvijek na njegovu adresu (poslužitelj prepisuje adresu), **20 čitanja** (granica troška), istek 7 dana; Attio dobiva bilješku „SAM koristi probu”.
- Kodovi u data/pristupi.json (atomično pisanje). Isti posjetitelj dvaput = isti kod.
