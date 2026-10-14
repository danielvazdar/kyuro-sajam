// Kyuro sajam — F1 demo. Jedan ekran, četiri koraka: fotografija → računi → eURA.txt → mail.
// Stanje se nikad ne mijenja na mjestu: svaka radnja gradi novo i iscrtava ga.

const MAKS_STRANICA = 2400 // isto kao poslužitelj; manja datoteka = brže preko mobilnih podataka
const KLJUC_IZLAZA = 'sajam-izlaz' // mailovi koji nisu otišli zbog mreže

const POLJA = [
  { ime: 'dobavljac', oznaka: 'Dobavljač', vrsta: 'text', siroko: true },
  { ime: 'oib_dobavljaca', oznaka: 'OIB dobavljača', vrsta: 'text', znamenke: true },
  { ime: 'broj_racuna', oznaka: 'Broj računa', vrsta: 'text' },
  { ime: 'datum_racuna', oznaka: 'Datum računa', vrsta: 'date' },
  { ime: 'datum_dospijeca', oznaka: 'Dospijeće', vrsta: 'date' },
  { ime: 'ukupno', oznaka: 'Ukupno €', vrsta: 'iznos' },
  { ime: 'bez_pdv', oznaka: 'Ne podliježe PDV-u', vrsta: 'iznos' },
  { ime: 'osnovica25', oznaka: 'Osnovica 25 %', vrsta: 'iznos' },
  { ime: 'pdv25', oznaka: 'PDV 25 %', vrsta: 'iznos' },
  { ime: 'osnovica13', oznaka: 'Osnovica 13 %', vrsta: 'iznos' },
  { ime: 'pdv13', oznaka: 'PDV 13 %', vrsta: 'iznos' },
  { ime: 'osnovica5', oznaka: 'Osnovica 5 %', vrsta: 'iznos' },
  { ime: 'pdv5', oznaka: 'PDV 5 %', vrsta: 'iznos' },
  { ime: 'napomena', oznaka: 'Napomena', vrsta: 'text', siroko: true },
]
const IZNOSI = new Set(POLJA.filter((p) => p.vrsta === 'iznos').map((p) => p.ime))

const $ = (id) => document.getElementById(id)
const KORACI = ['korak-foto', 'korak-citanje', 'korak-racuni', 'korak-datoteka', 'korak-poslano']

let stanje = { korak: 'korak-foto', sesija: null, racuni: [], uklonjen: null, otvoren: null }

function postavi(izmjene) {
  stanje = { ...stanje, ...izmjene }
  iscrtaj()
}

// ── pomoćno ─────────────────────────────────────────────────────────────────
const eur = (iznos) =>
  new Intl.NumberFormat('hr-HR', { style: 'currency', currency: 'EUR' }).format(Number(iznos) || 0)

function poruka(tekst) {
  $('greska').textContent = tekst
  $('greska').hidden = !tekst
}

class GreskaPoslužitelja extends Error {}

async function api(putanja, opcije) {
  let odgovor
  try {
    odgovor = await fetch(putanja, { credentials: 'same-origin', ...opcije })
  } catch {
    throw new TypeError('mreža')
  }
  if (odgovor.status === 401) throw new GreskaPoslužitelja('Prijava je istekla. Osvježite stranicu.')
  if (!odgovor.ok) {
    const tijelo = await odgovor.json().catch(() => ({}))
    const detalj = typeof tijelo.detail === 'string' ? tijelo.detail : 'Nešto nije u redu. Pokušajte ponovno.'
    throw new GreskaPoslužitelja(detalj)
  }
  return odgovor
}

const jeLiCist = (r) => r.upozorenja.length === 0 && r.nesigurno.length === 0
const bezProvjera = ({ upozorenja: _upozorenja, ...racun }) => racun

// ── 1. fotografija ──────────────────────────────────────────────────────────
async function smanji(datoteka) {
  try {
    const slika = await createImageBitmap(datoteka, { imageOrientation: 'from-image' })
    const omjer = Math.min(1, MAKS_STRANICA / Math.max(slika.width, slika.height))
    const platno = document.createElement('canvas')
    platno.width = Math.round(slika.width * omjer)
    platno.height = Math.round(slika.height * omjer)
    platno.getContext('2d').drawImage(slika, 0, 0, platno.width, platno.height)
    slika.close()
    return await new Promise((gotovo) => platno.toBlob((b) => gotovo(b || datoteka), 'image/jpeg', 0.88))
  } catch {
    return datoteka // stariji preglednik: poslužitelj ionako smanjuje
  }
}

async function ucitajFotografiju(dogadaj) {
  const datoteka = dogadaj.target.files?.[0]
  dogadaj.target.value = ''
  if (!datoteka) return
  poruka('')
  const pregled = URL.createObjectURL(datoteka)
  $('pregled-foto').src = pregled
  postavi({ korak: 'korak-citanje' })

  const pocetak = Date.now()
  const sat = setInterval(() => {
    $('citanje-sekunde').textContent = `${Math.round((Date.now() - pocetak) / 1000)} s`
  }, 500)
  try {
    const obrazac = new FormData()
    obrazac.append('fotografija', await smanji(datoteka), 'fotografija.jpg')
    const odgovor = await api('api/procitaj', { method: 'POST', body: obrazac })
    const { sesija, racuni } = await odgovor.json()
    if (racuni.length === 0) {
      postavi({ korak: 'korak-foto' })
      poruka('Na fotografiji nisam našao nijedan račun. Pokušajte bliže i s više svjetla.')
      return
    }
    postavi({ korak: 'korak-racuni', sesija, racuni, uklonjen: null, otvoren: null })
  } catch (greska) {
    postavi({ korak: 'korak-foto' })
    poruka(greska instanceof TypeError ? 'Nema interneta. Provjerite mrežu i fotografirajte ponovno.' : greska.message)
  } finally {
    clearInterval(sat)
    URL.revokeObjectURL(pregled)
  }
}

// ── 2. računi ───────────────────────────────────────────────────────────────
function iscrtajSazetak() {
  const cisti = stanje.racuni.filter(jeLiCist).length
  const ukupno = stanje.racuni.reduce((zbroj, r) => zbroj + Number(r.ukupno), 0)
  $('sazetak').replaceChildren(
    brojka(String(stanje.racuni.length), 'dokumenata', ''),
    brojka(String(stanje.racuni.length - cisti), 'za provjeru', stanje.racuni.length - cisti ? 'pazi' : 'dobro'),
    brojka(eur(ukupno), 'ukupno', ''),
  )
}

function brojka(vrijednost, opis, ton) {
  const el = document.createElement('div')
  el.className = `brojka ${ton}`
  const b = document.createElement('b')
  b.className = 'tnum'
  b.textContent = vrijednost
  const s = document.createElement('span')
  s.textContent = opis
  el.append(b, s)
  return el
}

function poljeZaUnos(racun, polje) {
  const oznaka = document.createElement('label')
  if (polje.siroko) oznaka.className = 'siroko'
  oznaka.textContent = polje.oznaka
  const unos = document.createElement('input')
  unos.name = polje.ime
  if (polje.vrsta === 'iznos') {
    unos.type = 'text'
    unos.inputMode = 'decimal'
    unos.value = String(racun[polje.ime]).replace('.', ',')
  } else {
    unos.type = polje.vrsta
    unos.value = racun[polje.ime] ?? ''
    if (polje.znamenke) unos.inputMode = 'numeric'
  }
  if (racun.nesigurno.includes(polje.ime)) unos.classList.add('nesigurno')
  oznaka.append(unos)
  return oznaka
}

function iscrtajRacun(racun, indeks) {
  const el = $('predlozak-racun').content.firstElementChild.cloneNode(true)
  const cist = jeLiCist(racun)
  el.classList.toggle('pazi', !cist)
  el.querySelector('.racun-vrsta').textContent = racun.vrsta === 'slip' ? 'Slip' : 'R1'
  el.querySelector('.racun-ime').textContent = racun.dobavljac || 'Nepoznat dobavljač'
  el.querySelector('.racun-iznos').textContent = eur(racun.ukupno)
  const stanjeEl = el.querySelector('.racun-stanje')
  stanjeEl.textContent = cist
    ? `✓ ${racun.broj_racuna} · OIB i zbrojevi u redu`
    : `Za provjeru: ${racun.upozorenja.length + racun.nesigurno.length} ${racun.broj_racuna ? '· ' + racun.broj_racuna : ''}`
  stanjeEl.classList.add(cist ? 'dobro' : 'pazi')

  const otvoren = stanje.otvoren === indeks
  const glava = el.querySelector('.racun-glava')
  glava.setAttribute('aria-expanded', String(otvoren))
  glava.addEventListener('click', () => postavi({ otvoren: otvoren ? null : indeks }))
  el.querySelector('.racun-detalji').hidden = !otvoren
  if (otvoren) {
    const nalazi = [
      ...racun.upozorenja,
      ...racun.nesigurno.map((ime) => `Nesigurno očitano: ${POLJA.find((p) => p.ime === ime)?.oznaka ?? ime}`),
    ]
    el.querySelector('.racun-nalazi').replaceChildren(...nalazi.map((tekst) => {
      const li = document.createElement('li')
      li.textContent = tekst
      return li
    }))
    el.querySelector('.polja').replaceChildren(...POLJA.map((p) => poljeZaUnos(racun, p)))
    el.querySelector('.spremi').addEventListener('click', () => spremiIzmjene(indeks, el))
    el.querySelector('.ukloni').addEventListener('click', () => ukloni(indeks))
  }
  return el
}

async function spremiIzmjene(indeks, el) {
  const unosi = Object.fromEntries([...el.querySelectorAll('.polja input')].map((u) => [u.name, u.value.trim()]))
  const izmijenjen = { ...bezProvjera(stanje.racuni[indeks]), ...unosi, nesigurno: [] }
  for (const ime of IZNOSI) izmijenjen[ime] = (izmijenjen[ime] || '0').replace(/\s/g, '').replace(',', '.')
  if (!izmijenjen.datum_dospijeca) izmijenjen.datum_dospijeca = null
  try {
    const odgovor = await api('api/provjeri', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ racuni: [izmijenjen] }),
    })
    const [provjeren] = (await odgovor.json()).racuni
    postavi({ racuni: stanje.racuni.map((r, i) => (i === indeks ? provjeren : r)), otvoren: null })
    poruka('')
  } catch (greska) {
    poruka(greska instanceof TypeError ? 'Nema interneta — izmjena nije spremljena.' : 'Neko polje nije ispravno (datum ili iznos).')
  }
}

function ukloni(indeks) {
  postavi({
    racuni: stanje.racuni.filter((_, i) => i !== indeks),
    uklonjen: { racun: stanje.racuni[indeks], indeks },
    otvoren: null,
  })
}

function vrati() {
  const { racun, indeks } = stanje.uklonjen
  postavi({
    racuni: [...stanje.racuni.slice(0, indeks), racun, ...stanje.racuni.slice(indeks)],
    uklonjen: null,
  })
}

// ── 2b. datoteka ────────────────────────────────────────────────────────────
async function slozi() {
  $('slozi').disabled = true
  try {
    const odgovor = await api('api/eura', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ racuni: stanje.racuni.map(bezProvjera) }),
    })
    const tekst = await odgovor.text()
    $('datoteka').textContent = tekst.replaceAll('\r\n', '\n')
    const stari = $('preuzmi').href
    if (stari.startsWith('blob:')) URL.revokeObjectURL(stari)
    $('preuzmi').href = URL.createObjectURL(new Blob([tekst], { type: 'text/plain' }))
    postavi({ korak: 'korak-datoteka' })
    poruka('')
  } catch (greska) {
    poruka(greska instanceof TypeError ? 'Nema interneta. Pokušajte ponovno.' : greska.message)
  } finally {
    $('slozi').disabled = false
  }
}

// ── 3. slanje ───────────────────────────────────────────────────────────────
function citajIzlaz() {
  try { return JSON.parse(localStorage.getItem(KLJUC_IZLAZA) || '[]') } catch { return [] }
}

function spremiIzlaz(popis) {
  try { localStorage.setItem(KLJUC_IZLAZA, JSON.stringify(popis)) } catch { /* pun ili zabranjen */ }
  iscrtajIzlaz()
}

function iscrtajIzlaz() {
  const popis = citajIzlaz()
  $('izlaz').hidden = popis.length === 0
  if (popis.length === 0) return
  const gumb = document.createElement('button')
  gumb.type = 'button'
  gumb.className = 'tekst-gumb'
  gumb.textContent = 'Pošalji sada'
  gumb.addEventListener('click', isprazniIzlaz)
  $('izlaz').replaceChildren(`${popis.length} mail(ova) čeka internet. `, gumb)
}

async function posaljiJedan(tijelo) {
  const odgovor = await api('api/posalji', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tijelo),
  })
  return odgovor.json()
}

async function isprazniIzlaz() {
  const ostali = []
  for (const tijelo of citajIzlaz()) {
    try {
      await posaljiJedan(tijelo)
    } catch (greska) {
      if (greska instanceof TypeError) ostali.push(tijelo) // i dalje nema mreže
      // greška poslužitelja (npr. kriva adresa) se ne ponavlja beskonačno
    }
  }
  spremiIzlaz(ostali)
}

async function posalji(dogadaj) {
  dogadaj.preventDefault()
  const obrazac = $('obrazac')
  const podaci = new FormData(obrazac)
  const email = String(podaci.get('email') || '').trim()
  const greskaEl = $('obrazac-greska')
  const pokazi = (tekst) => { greskaEl.textContent = tekst; greskaEl.hidden = !tekst }

  if (!obrazac.elements.email.checkValidity() || !email) return pokazi('Upišite ispravnu e-mail adresu.')
  if (!podaci.get('privola')) return pokazi('Za slanje je potrebna privola.')
  pokazi('')

  const tijelo = {
    sesija: stanje.sesija,
    racuni: stanje.racuni.map(bezProvjera),
    email,
    ime: String(podaci.get('ime') || '').trim(),
    tvrtka: String(podaci.get('tvrtka') || '').trim(),
    privola: true,
  }
  $('posalji').disabled = true
  try {
    const { attio } = await posaljiJedan(tijelo)
    $('poslano-tekst').textContent = `Datoteke su na putu prema ${email}.`
    $('poslano-attio').hidden = attio
    postavi({ korak: 'korak-poslano' })
  } catch (greska) {
    if (greska instanceof TypeError) {
      spremiIzlaz([...citajIzlaz(), tijelo])
      $('poslano-tekst').textContent = `Nema interneta — mail za ${email} je spremljen i otići će čim se veza vrati.`
      $('poslano-attio').hidden = true
      postavi({ korak: 'korak-poslano' })
    } else {
      pokazi(greska.message)
    }
  } finally {
    $('posalji').disabled = false
  }
}

function noviPosjetitelj() {
  $('obrazac').reset()
  $('obrazac-greska').hidden = true
  postavi({ korak: 'korak-datoteka' })
}

function ispocetka() {
  $('obrazac').reset()
  poruka('')
  postavi({ korak: 'korak-foto', sesija: null, racuni: [], uklonjen: null, otvoren: null })
}

// ── iscrtavanje ─────────────────────────────────────────────────────────────
function iscrtaj() {
  for (const id of KORACI) $(id).hidden = id !== stanje.korak
  $('ispocetka').hidden = stanje.korak === 'korak-foto' || stanje.korak === 'korak-citanje'
  if (stanje.korak === 'korak-racuni') {
    iscrtajSazetak()
    $('racuni').replaceChildren(...stanje.racuni.map(iscrtajRacun))
    $('vrati-traka').hidden = !stanje.uklonjen
    $('slozi').disabled = stanje.racuni.length === 0
  }
  window.scrollTo({ top: 0 })
}

$('kamera').addEventListener('change', ucitajFotografiju)
$('galerija').addEventListener('change', ucitajFotografiju)
$('vrati').addEventListener('click', vrati)
$('slozi').addEventListener('click', slozi)
$('natrag-racuni').addEventListener('click', () => postavi({ korak: 'korak-racuni' }))
$('obrazac').addEventListener('submit', posalji)
$('isti-list').addEventListener('click', noviPosjetitelj)
$('novi-list').addEventListener('click', ispocetka)
$('ispocetka').addEventListener('click', ispocetka)
window.addEventListener('online', isprazniIzlaz)

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* bez offline ljuske, aplikacija i dalje radi */ })
}
iscrtajIzlaz()
iscrtaj()
