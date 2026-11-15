# Timișoara Traffic Stress Tester

[Română](#română) · [English](#english)

---

## Română

### Despre proiect

Un instrument pentru **Primăria Municipiului Timișoara** care arată ce se întâmplă cu
traficul din zona **Calea Martirilor / Strada Cluj** când schimbi o stradă: o închizi pentru mașini sau dai o bandă
auto autobuzului, bicicletelor ori trotuarului.

Aplicația găsește străzile unde, dacă iei loc mașinilor, traficul din zonă devine **mai rapid** (paradoxul Braess),
schimbările care aproape nu costă nimic șoferii și pe cele care ar bloca zona. Nu înlocuiește un studiu de trafic: arată
care idei merită unul.

Destinatari: **Direcția Generală de Investiții și Mentenanță** (modificări de străzi) și **SMTT / STPT** (benzi de autobuz).

### Ce poți face

- Alegi o stradă și modifici benzile; harta și rezultatele se actualizează imediat.
- Vezi timpul total petrecut în trafic, rutele afectate (în secunde), unde se mută traficul, așteptarea la intersecții
  și liniile STPT de pe stradă.
- Compari dimineața, prânzul și seara: o măsură bună la ora de vârf poate fi inutilă la prânz.
- Primești o listă de variante optimizate: străzi unde apare paradoxul Braess și un pachet recomandat.
- Vezi câți șoferi ar trebui să treacă la autobuz sau bicicletă pentru ca o bandă luată să nu coste nimic.

### Surse de date

| Sursă | Pentru ce |
|---|---|
| OpenStreetMap (© OpenStreetMap contributors, ODbL) | Străzi, benzi, semafoare, reguli de viraj, clădiri și puncte de interes |
| `cont.primariatm.ro/api/mobile/transit/network` | Liniile STPT de pe coridor și traseele lor |
| `cont.primariatm.ro/api/mobile/transit/stops/{id}/timetable` | Câte autobuze trec pe oră în intervalul simulat |
| `cont.primariatm.ro/api/mobile/wallet/types?category=transport` | Prețul biletelor |
| `cont.primariatm.ro/api/mobile/parking` | Tarifele Timpark și străzile cu parcare plătită din zonă |
| PMUD Timișoara | Ponderea deplasărilor cu mașina |
| Sondajul nostru (31 de persoane, anonim) | Vezi mai jos |
| Cairns, Atkins și Goodwin (2002) | Opțiunea „evaporarea traficului” |
| OpenFreeMap | Harta de fundal |

API-urile Primăriei sunt apelate doar din backend și păstrate în cache. Dacă unul nu răspunde, acea parte lipsește din
aplicație; nu se inventează nimic. Traficul este **estimat** (din clădiri și puncte de interes), iar aplicația spune asta.

### Sondajul cetățenilor

Am întrebat 31 de oameni din Timișoara cum se deplasează prin zonă: cu ce merg la serviciu sau la facultate, câte
persoane sunt în mașină, la ce oră pleacă, dacă folosesc Waze sau Google Maps și scurtăturile lor, pe ce străzi ocolesc
Calea Martirilor și Strada Cluj și cu cât ar trebui să fie mai rapid autobuzul ca să lase mașina.

Răspunsurile sunt folosite în aplicație, pentru acuratețe:

- **verifică ipotezele modelului**: ponderea mașinii (42% în sondaj) și numărul de persoane pe mașină, comparate cu
  datele PMUD; de la 100 de răspunsuri, valorile din sondaj le înlocuiesc automat pe cele presupuse;
- **apar lângă rezultate**: lângă fiecare bandă de autobuz, aplicația arată câți dintre cei întrebați ar renunța la
  mașină pentru câștigul de timp obținut;
- **străzile numite de oameni** ca scurtături sunt comparate cu cele găsite de aplicație (de exemplu Strada Cozia).

Sondajul este anonim (doar cartierul și ora răspunsului) și se află în `backend/data/survey/`.

### Pornire

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000                    # pregătește căutarea Braess pentru fiecare interval (~1 min)

# frontend (Node 20+), în alt terminal
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (trimite /api către :8000)
```

Docker: `docker compose up --build` (interfața pe http://localhost:8080, documentația API pe http://localhost:8000/docs).

Teste: `cd backend && pytest -q` (64 de teste, fără internet).

### Limite

- Traficul este estimat, nu măsurat; numărătorile de trafic din `backend/data/corridor/` îl calibrează.
- Tramvaiele și traficul de biciclete nu sunt încă modelate.

### Licență

MIT. Vezi [`LICENSE`](LICENSE).

---

## English

### About

A tool for **Timișoara City Hall** that shows what happens to traffic around **Calea Martirilor /
Strada Cluj** when you change a street: close it to cars, or give a car lane to buses, bikes or the sidewalk.

It finds the streets where taking space from cars makes traffic in the area **faster** (Braess's paradox), the changes
that cost drivers almost nothing, and the ones that would jam the area. It doesn't replace a traffic study: it shows
which ideas deserve one.

Intended owners: **Direcția Generală de Investiții și Mentenanță** (street changes) and **SMTT / STPT** (bus lanes).

### What you can do

- Pick a street and change its lanes; the map and the results update at once.
- See total time in traffic, the routes affected (in seconds), where traffic moves, waits at intersections and the STPT
  lines on the street.
- Compare morning, midday and evening: a measure that helps at rush hour can be useless at midday.
- Get a list of optimized options: streets where Braess's paradox appears and a recommended package.
- See how many drivers would have to switch to the bus or bike for a lost lane to cost nothing.

### Data sources

| Source | Used for |
|---|---|
| OpenStreetMap (© OpenStreetMap contributors, ODbL) | Streets, lanes, traffic lights, turn rules, buildings and points of interest |
| `cont.primariatm.ro/api/mobile/transit/network` | STPT lines on the corridor and their routes |
| `cont.primariatm.ro/api/mobile/transit/stops/{id}/timetable` | Buses per hour in the simulated time window |
| `cont.primariatm.ro/api/mobile/wallet/types?category=transport` | Ticket prices |
| `cont.primariatm.ro/api/mobile/parking` | Timpark tariffs and paid street parking in the area |
| PMUD Timișoara | Share of trips made by car |
| Our survey (31 people, anonymous) | See below |
| Cairns, Atkins and Goodwin (2002) | The "traffic evaporation" option |
| OpenFreeMap | Base map |

City Hall APIs are called from the backend only and cached. If one doesn't answer, that part is left out of the app;
nothing is invented. Traffic is **estimated** (from buildings and points of interest), and the app says so.

### Citizen survey

We asked 31 people in Timișoara how they travel through the area: how they get to work or university, how many people
ride in their car, when they leave home, whether they use Waze or Google Maps and follow its shortcuts, which streets
they use to avoid Calea Martirilor and Strada Cluj, and how much faster the bus would have to be for them to leave the car.

Their answers are used in the app, for accuracy:

- **they check the model's assumptions**: the share of car trips (42% in the survey) and people per car, compared with
  the PMUD figures; from 100 answers, the survey values replace the assumed ones automatically;
- **they appear next to the results**: for every bus lane, the app shows how many respondents would leave the car for
  the time it saves;
- **the streets people named** as shortcuts are compared with the ones the app finds (for example Strada Cozia).

The survey is anonymous (only the neighbourhood and the time of the answer) and is in `backend/data/survey/`.

### Run it

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000                    # warms the Braess search for every time window (~1 min)

# frontend (Node 20+), in another terminal
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (proxies /api to :8000)
```

Docker: `docker compose up --build` (UI on http://localhost:8080, API docs on http://localhost:8000/docs).

Tests: `cd backend && pytest -q` (64 tests, offline).

### Limits

- Traffic is estimated, not measured; traffic counts in `backend/data/corridor/` calibrate it.
- Trams and cycling demand are not modelled yet.

### Licence

MIT. See [`LICENSE`](LICENSE).
