# DECISIONS

## 2026-10-14 — sajamski demo kao zaseban servis
- Zaseban repo, ne modul u kyuro-demo: demo je statičan bez mreže (tvrda granica), ovo mora čitati, slati i pisati u CRM.
- Putanja `demo.kyuro.tech/sajam/` umjesto nove poddomene: ista lozinka, postojeći certifikat, bez DNS izmjene dva dana prije sajma.
- Jedna fotografija cijelog lista (Daniel). Čitač: `claude-opus-5-5`, effort medium, `fallbacks: "default"`. Trošak ~1–3 centa po listu (Daniel odobrio).
- eURA emiter prenesen u Python 1:1 iz kyuro-demo; testovi drže iste položaje polja.
- Attio: posao „<tvrtka> — Accept sajam 2026" u fazi Lead, vrijednost prazna; postojeća osoba se ne prepisuje.
- PWA (Daniel): ljuska radi offline; mail bez mreže čeka u lokalnom redu i šalje se kad se veza vrati.
- Ključevi na KVM1 (`/home/daniel/kyuro-sajam/.env`) kopirani iz webinar-funnela uz Danielov pristanak (14.10.), samo za sajam. Poslije sajma: vlastiti ključevi (issue).
