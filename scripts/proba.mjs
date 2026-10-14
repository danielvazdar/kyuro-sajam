// E2E proba sučelja na mobilnom ekranu: fotografija → računi → izmjena → eURA.txt → slanje.
// Pravi backend (provjeri, eura); čitač i slanje su podmetnuti — bez troška i bez maila.
// Pokretanje: node scripts/proba.mjs http://127.0.0.1:8021/   (snimke idu u ./snimke/)
import { mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(`${process.env.HOME}/PROJECT/KYURO/demo/package.json`)
const { chromium, devices } = require('playwright')

const ADRESA = process.argv[2] ?? 'http://127.0.0.1:8021/'
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
stranica.on('console', (p) => p.type() === 'error' && greske.push(p.text()))

await stranica.route('**/api/procitaj', async (ruta) => {
  await new Promise((r) => setTimeout(r, 1500))
  await ruta.fulfill({ json: OCITANO })
})
let poslano = null
await stranica.route('**/api/posalji', async (ruta) => {
  poslano = ruta.request().postDataJSON()
  await ruta.fulfill({ json: { poslano: true, attio: true } })
})

const tvrdi = (uvjet, poruka) => { if (!uvjet) throw new Error(`✗ ${poruka}`) }

await stranica.goto(ADRESA)
await stranica.screenshot({ path: 'snimke/1-pocetak.png' })

// 1×1 JPEG je dovoljan: čitač je podmetnut
const jpeg = Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==', 'base64')
await stranica.setInputFiles('#galerija', { name: 'list.jpg', mimeType: 'image/jpeg', buffer: jpeg })
await stranica.waitForSelector('#korak-citanje:not([hidden])')
await stranica.screenshot({ path: 'snimke/2-citanje.png' })

await stranica.waitForSelector('#korak-racuni:not([hidden])')
tvrdi(await stranica.locator('.racun').count() === 3, 'tri računa na ekranu')
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

await stranica.click('#posalji')
tvrdi(await stranica.isVisible('#obrazac-greska'), 'prazna adresa je odbijena')
await stranica.fill('input[name=email]', 'ana@ured.hr')
await stranica.fill('input[name=ime]', 'Ana Horvat')
await stranica.fill('input[name=tvrtka]', 'Ured Horvat d.o.o.')
await stranica.click('#posalji')
tvrdi(await stranica.textContent('#obrazac-greska') === 'Za slanje je potrebna privola.', 'bez privole nema slanja')
await stranica.check('input[name=privola]')
await stranica.click('#posalji')
await stranica.waitForSelector('#korak-poslano:not([hidden])')
tvrdi(poslano?.email === 'ana@ured.hr' && poslano.racuni.length === 3, 'poslan pravi sadržaj')
tvrdi(poslano.racuni.every((r) => !('upozorenja' in r)), 'upozorenja se ne šalju natrag')
await stranica.screenshot({ path: 'snimke/6-poslano.png' })

await stranica.click('#isti-list')
tvrdi(await stranica.inputValue('input[name=email]') === '', 'obrazac očišćen za novog posjetitelja')

await preglednik.close()
tvrdi(greske.length === 0, `greške u konzoli: ${greske.join(' | ')}`)
console.log('✓ e2e proba prošla')
