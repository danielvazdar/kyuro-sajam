// E2E proba sučelja na mobilnom ekranu: fotografija → računi → izmjena → eURA.txt → slanje.
// Pravi backend (provjeri, eura); čitač i slanje su podmetnuti — bez troška i bez maila.
// Pokretanje: node scripts/proba.mjs http://localhost:8021/ [lozinka]   (snimke idu u ./snimke/)
// Backend mora imati SAJAM_LOZINKA_HASH za tu lozinku (zadano: „proba”).
import { mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(`${process.env.HOME}/PROJECT/KYURO/demo/package.json`)
const { chromium, devices } = require('playwright')

const ADRESA = process.argv[2] ?? 'http://localhost:8021/'
const LOZINKA = process.argv[3] ?? 'proba'
mkdirSync('snimke', { recursive: true })

const racun = (izmjene) => ({
  vrsta: 'racun', dobavljac: 'INA d.d.', oib_dobavljaca: '10493141768', broj_racuna: '4471/1/2',
  datum_racuna: '2026-10-01', datum_dospijeca: '2026-10-16', ukupno: '64.50', bez_pdv: '0.00',
  osnovica5: '0.00', pdv5: '0.00', osnovica13: '0.00', pdv13: '0.00', osnovica25: '51.60',
  pdv25: '12.90', napomena: 'Gorivo', nesigurno: [], upozorenja: [], ...izmjene,
})
const OCITANO = {
  sesija: 'a'.repeat(32),
  racuni: [
    racun({}),
    racun({ vrsta: 'slip', dobavljac: 'Konzum plus d.o.o.', oib_dobavljaca: '62226620908',
      broj_racuna: '118/PJ12/4', ukupno: '23.87', osnovica25: '9.20', pdv25: '2.30',
      osnovica5: '11.78', pdv5: '0.59', napomena: 'Potrošni materijal' }),
    racun({ dobavljac: 'Tisak d.d.', oib_dobavljaca: '32497856000', broj_racuna: '',
      ukupno: '15.00', osnovica25: '12.00', pdv25: '3.00', nesigurno: ['broj_racuna'],
      upozorenja: ['OIB dobavljača nije ispravan (kontrolna znamenka)', 'Nedostaje broj računa'] }),
  ],
}

const greske = []
const preglednik = await chromium.launch()
const stranica = await preglednik.newPage({ ...devices['iPhone 13'] })
stranica.on('pageerror', (g) => greske.push(String(g)))
// 401 je očekivan dio probe prijave (prvo otvaranje, kriva lozinka); sve ostalo je greška.
stranica.on('console', (p) => p.type() === 'error' && !p.text().includes('status of 401') && greske.push(p.text()))

// Dvije fotografije: prva nosi INA + Konzum, druga Tisak i ponovno INA (preklapanje kadra)
let citanja = 0
await stranica.route('**/api/procitaj', async (ruta) => {
  const broj = citanja++
  await new Promise((r) => setTimeout(r, 1200))
  const [ina, konzum, tisak] = OCITANO.racuni
  await ruta.fulfill({ json: broj === 0
    ? { sesija: 'a'.repeat(32), racuni: [ina, konzum] }
    : { sesija: 'b'.repeat(32), racuni: [tisak, ina] } })
})
const leadovi = []
await stranica.route('**/api/lead', async (ruta) => {
  leadovi.push(ruta.request().postDataJSON())
  await ruta.fulfill({ json: { ok: true, attio: true } })
})
let poslano = null
await stranica.route('**/api/posalji', async (ruta) => {
  poslano = ruta.request().postDataJSON()
  await ruta.fulfill({ json: { poslano: true, attio: true } })
})

const tvrdi = (uvjet, poruka) => { if (!uvjet) throw new Error(`✗ ${poruka}`) }

await stranica.goto(ADRESA)
await stranica.waitForSelector('#korak-prijava:not([hidden])')
await stranica.fill('input[name=lozinka]', 'kriva')
await stranica.click('#prijava-gumb')
await stranica.waitForSelector('#prijava-greska:not([hidden])')
tvrdi((await stranica.textContent('#prijava-greska')).startsWith('Kriva lozinka ili kod'), 'kriva lozinka odbijena')
await stranica.screenshot({ path: 'snimke/0-prijava.png' })
await stranica.fill('input[name=lozinka]', LOZINKA)
await stranica.click('#prijava-gumb')
await stranica.waitForSelector('#korak-posjetitelj:not([hidden])')
await stranica.waitForTimeout(400)
await stranica.screenshot({ path: 'snimke/1-pocetak.png' })

// Drugo otvaranje: kolačić vrijedi, prijava se ne smije pojaviti
await stranica.reload()
await stranica.waitForTimeout(800)
tvrdi(await stranica.isHidden('#korak-prijava'), 'prijava zapamćena nakon ponovnog otvaranja')

// PRVI korak je posjetitelj: bez adrese i privole demo ne kreće
await stranica.click('#zapocni')
tvrdi(await stranica.isVisible('#obrazac-greska'), 'prazna adresa je odbijena')
await stranica.fill('input[name=email]', 'ana@ured.hr')
await stranica.fill('input[name=ime]', 'Ana Horvat')
await stranica.fill('input[name=tvrtka]', 'Ured Horvat d.o.o.')
await stranica.click('#zapocni')
tvrdi(await stranica.textContent('#obrazac-greska') === 'Za nastavak je potrebna privola.', 'bez privole nema demonstracije')
await stranica.check('input[name=privola]')
await stranica.click('#zapocni')
// Tri ekrana dobrodošlice odmah nakon podataka
await stranica.waitForSelector('#korak-dobrodoslica:not([hidden])')
await stranica.waitForTimeout(300)
await stranica.screenshot({ path: 'snimke/1a-dobrodoslica.png' })
await stranica.click('#dalje')
await stranica.click('#dalje')
tvrdi(await stranica.textContent('#dalje') === 'Krenimo', 'zadnji ekran ima Krenimo')
await stranica.click('#dalje')
await stranica.waitForSelector('#korak-foto:not([hidden])')
tvrdi(leadovi.length === 1 && leadovi[0].email === 'ana@ured.hr', 'lead upisan PRIJE demonstracije')
tvrdi((await stranica.textContent('#za-koga')).includes('Ana Horvat'), 'vidi se za koga je demo')
await stranica.waitForTimeout(400)
await stranica.screenshot({ path: 'snimke/1b-foto.png' })

// 1×1 JPEG je dovoljan: čitač je podmetnut
const jpeg = Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==', 'base64')
await stranica.setInputFiles('#galerija', [
  { name: 'list-1.jpg', mimeType: 'image/jpeg', buffer: jpeg },
  { name: 'list-2.jpg', mimeType: 'image/jpeg', buffer: jpeg },
])
await stranica.waitForSelector('#korak-citanje:not([hidden])')
await stranica.screenshot({ path: 'snimke/2-citanje.png' })

await stranica.waitForSelector('#korak-racuni:not([hidden])')
tvrdi(await stranica.locator('.racun').count() === 3, 'tri računa s dvije fotografije, duplikat izbačen')
await stranica.screenshot({ path: 'snimke/3-racuni.png', fullPage: true })

// Ispravi treći račun: pravi backend mora ponovno provjeriti
await stranica.locator('.racun-glava').nth(2).click()
await stranica.screenshot({ path: 'snimke/4-ispravak.png', fullPage: true })
await stranica.fill('.racun-detalji:not([hidden]) input[name=oib_dobavljaca]', '10493141768')
await stranica.fill('.racun-detalji:not([hidden]) input[name=broj_racuna]', '77/1/1')
await stranica.click('.racun-detalji:not([hidden]) .spremi')
await stranica.waitForFunction(() => document.querySelectorAll('.racun.pazi').length === 0)

// Ukloni pa vrati
await stranica.locator('.racun-glava').first().click()
await stranica.click('.racun-detalji:not([hidden]) .ukloni')
tvrdi(await stranica.locator('.racun').count() === 2, 'uklonjen račun')
await stranica.click('#vrati')
tvrdi(await stranica.locator('.racun').count() === 3, 'vraćen račun')

await stranica.click('#slozi')
await stranica.waitForSelector('#korak-datoteka:not([hidden])')
const datoteka = await stranica.textContent('#datoteka')
const retci = datoteka.split('\n').filter(Boolean)
tvrdi(retci.length === 3 && retci.every((r) => r.length === 211), 'eURA: 3 retka po 211 znakova')
await stranica.waitForTimeout(400) // pričekaj animaciju ulaska
await stranica.screenshot({ path: 'snimke/5-datoteka.png', fullPage: true })

tvrdi(await stranica.textContent('#posalji') === 'Pošalji na ana@ured.hr', 'jedan dodir do slanja')
await stranica.click('#posalji')
await stranica.waitForSelector('#korak-poslano:not([hidden])')
tvrdi(poslano?.email === 'ana@ured.hr' && poslano.racuni.length === 3, 'poslan pravi sadržaj')
tvrdi(JSON.stringify(poslano.sesije) === JSON.stringify(['a'.repeat(32), 'b'.repeat(32)]), 'obje fotografije idu u mail')
tvrdi(poslano.racuni.every((r) => !('upozorenja' in r)), 'upozorenja se ne šalju natrag')
await stranica.screenshot({ path: 'snimke/6-poslano.png' })

// Novi posjetitelj, isti računi: podaci prvo, pa ravno na popis bez ponovnog čitanja
await stranica.click('#isti-racuni')
await stranica.waitForSelector('#korak-posjetitelj:not([hidden])')
tvrdi(await stranica.inputValue('input[name=email]') === '', 'obrazac očišćen za novog posjetitelja')
await stranica.fill('input[name=email]', 'ivo@ured2.hr')
await stranica.check('input[name=privola]')
await stranica.click('#zapocni')
await stranica.waitForSelector('#korak-dobrodoslica:not([hidden])')
await stranica.click('#preskoci')
await stranica.waitForSelector('#korak-racuni:not([hidden])')
tvrdi(await stranica.locator('.racun').count() === 3, 'isti računi zadržani')
tvrdi(citanja === 2, 'bez ponovnog čitanja')
tvrdi(leadovi.length === 2, 'drugi posjetitelj je lead')

// ── Posjetitelj na probi: otvara poveznicu iz maila (?kod=), bez Danielove lozinke ──
const KOD = process.env.PROBNI_KOD
if (KOD) {
  const kontekst = await preglednik.newContext({ ...devices['iPhone 13'] })
  const gost = await kontekst.newPage()
  gost.on('pageerror', (g) => greske.push(String(g)))
  await gost.route('**/api/procitaj', (ruta) => ruta.fulfill({ json: { sesija: 'c'.repeat(32), racuni: [OCITANO.racuni[0]] } }))
  let gostPoslao = null
  await gost.route('**/api/posalji', async (ruta) => {
    gostPoslao = ruta.request().postDataJSON()
    await ruta.fulfill({ json: { poslano: true, attio: true } })
  })
  await gost.goto(`${ADRESA}?kod=${KOD}`)
  await gost.waitForSelector('#korak-dobrodoslica:not([hidden])')
  tvrdi(!(await gost.url()).includes('kod='), 'kod maknut iz adrese')
  await gost.click('#preskoci')
  await gost.waitForSelector('#korak-foto:not([hidden])')
  tvrdi((await gost.textContent('#proba-info')).includes('preostalo čitanja: 20'), 'vidi koliko mu ostaje')
  await gost.setInputFiles('#galerija', { name: 'a.jpg', mimeType: 'image/jpeg', buffer: jpeg })
  await gost.waitForSelector('#korak-racuni:not([hidden])')
  await gost.click('#slozi')
  await gost.waitForSelector('#korak-datoteka:not([hidden])')
  tvrdi((await gost.textContent('#posalji')).includes('gost@ured.hr'), 'šalje na svoju adresu')
  await gost.click('#posalji')
  await gost.waitForSelector('#korak-poslano:not([hidden])')
  tvrdi(gostPoslao?.email === 'gost@ured.hr', 'tijelo nosi njegovu adresu')
  tvrdi(await gost.isHidden('#isti-racuni'), 'gost nema „novi posjetitelj”')
  tvrdi(await gost.textContent('#novi-posjetitelj') === 'Novi list', 'gost dobiva „Novi list”')
  await gost.screenshot({ path: 'snimke/7-proba-poslano.png' })
  // drugi dolazak: bez dobrodošlice
  await gost.goto(ADRESA)
  await gost.waitForSelector('#korak-foto:not([hidden])')
  await kontekst.close()
}

await preglednik.close()
tvrdi(greske.length === 0, `greške u konzoli: ${greske.join(' | ')}`)
console.log('✓ e2e proba prošla')
