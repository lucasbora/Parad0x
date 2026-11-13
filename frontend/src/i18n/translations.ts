import { createContext, useContext } from "react";
import type { LaneUse } from "../types/corridor";

export type Lang = "ro" | "en";

const ro = {
  appName: "TM-BraessGreen",
  subtitle: "Simulator pe un coridor real",
  peak: "vârf dimineață",
  explain: "Ce este paradoxul Braess?",
  language: "Limba",
  loading: "Se încarcă rețeaua…",
  backendDown: "Nu mă pot conecta la API. Pornește backend-ul (uvicorn) și reîncarcă pagina.",
  retry: "Reîncearcă",

  dataTitle: "Date de teren",
  dataReady: "Numărătorile sunt încărcate",
  dataMissing: "Rezultatele apar după ce încărcați numărătorile de trafic",
  dataMissingBody:
    "Modelul folosește rețeaua reală din OpenStreetMap, dar nu inventează trafic. Completați fișierele CSV din backend/data/corridor/ și reîncărcați pagina.",
  gatesCounted: "porți numărate",
  required: "obligatoriu",
  optional: "opțional",
  filePurpose: {
    "gate_counts.csv": "Mașini care intră (in) și ies (out) din zonă la fiecare poartă, în ora de vârf. Fără ele modelul nu are cerere reală și nu arată rezultate.",
    "turn_counts.csv": "Viraje stânga/înainte/dreapta la 2–3 intersecții cheie. Folosite doar pentru verificarea modelului (GEH).",
    "signal_timings.csv": "Ciclu și timp de verde pe fiecare acces (cronometru pe video e suficient). Altfel se folosește o valoare de manual, marcată ca ipoteză.",
    "lane_checks.csv": "Benzi auto verificate pe teren / Street View acolo unde OpenStreetMap greșește sau e nesigur.",
    "travel_times.csv": "Timpi de parcurs GPS pe coridor și pe alternativă. Folosiți doar pentru verificarea modelului.",
  } as Record<string, string>,
  showGates: "Unde trebuie numărat?",
  gatesHint: "Fiecare poartă: mașini care intră (in) și ies (out), 07:30–08:30, pe intervale de 15 min.",
  inLabel: "intră",
  outLabel: "ies",
  openMap: "hartă",

  step1: "1. Alege strada",
  chooseStreet: "Alege o stradă din zonă…",
  orClickMap: "sau dă click pe o stradă pe hartă",
  direction: "Sens",
  heading: { N: "spre nord", NE: "spre nord-est", E: "spre est", SE: "spre sud-est", S: "spre sud", SW: "spre sud-vest", W: "spre vest", NW: "spre nord-vest" } as Record<string, string>,
  segments: "segmente",
  carLanesNow: "benzi auto acum",
  fromOsm: "din OpenStreetMap",
  fieldCheck: "verificat pe teren",
  existingBusLane: "are deja bandă de autobuz",

  step2: "2. Modifică benzile",
  carLanesAfter: "Benzi auto după",
  removedBecomes: "Banda eliberată devine",
  uses: { bus: "Bandă autobuz", bike: "Pistă biciclete", sidewalk: "Trotuar / arbori", closed: "Închis pentru mașini" } as Record<LaneUse, string>,
  closedForCars: "Strada se închide pentru mașini",
  run: "Rulează simularea",
  running: "Se calculează…",
  noChange: "Alege mai puține benzi auto ca să existe o schimbare.",

  step3: "3. Rezultate",
  needsDataResults: "Fără numărători de trafic nu afișăm rezultate — orice cifră ar fi inventată.",
  totalTime: "Timp total petrecut în trafic în zonă",
  cars: "Mașini — timp pe rutele principale",
  buses: "Autobuze STPT pe acest coridor",
  busesPerHour: "autobuze/oră",
  noBuses: "Nicio linie STPT nu trece pe strada modificată.",
  shifts: "Unde se mută traficul",
  noShifts: "Traficul nu se mută semnificativ (sub 20 veh/h).",
  intersections: "Așteptare la intersecții",
  vehH: "veh/h",
  min: "min",
  s: "s",
  sensitivity: "Verifică robustețea (cerere ±20%)",
  sensitivityTitle: "Dacă cererea reală e cu 20% mai mică / mai mare",
  demand: "Cerere",
  total: "Total",
  mainRoute: "Ruta principală",
  bus: "Autobuz",

  assumptionsTitle: "Ipoteze folosite (până avem date)",
  calibrationTitle: "Verificare: model vs. realitate",
  calibrationMissing: "Adăugați turn_counts.csv (numărători pe viraje) și travel_times.csv pentru a verifica modelul.",
  gehHint: "GEH < 5 = potrivire bună (standard în ingineria traficului)",
  counted: "numărat",
  model: "model",
  observed: "observat",

  sources: "Surse",
  network: "Rețea",
  legendFlow: "Grosime = trafic",
  legendLess: "mai puțin trafic",
  legendMore: "mai mult trafic",
  legendSelected: "stradă aleasă",
  legendGateOk: "poartă numărată",
  legendGateMissing: "poartă fără date",
  legendSignal: "semafor",
  close: "Închide",

  explainerIntro:
    "Fiecare șofer alege drumul cel mai rapid pentru el. Uneori, o scurtătură atrage atât de mulți șoferi încât toată lumea ajunge mai târziu. Închide scurtătura și zona se mișcă mai repede!",
  explainerDemand: "Cerere (vehicule/oră)",
  explainerShortcut: "Scurtătura deschisă",
  explainerTravelTime: "Timp de deplasare pentru fiecare șofer",
  explainerTotal: "Timp total în rețea",
  explainerUpper: "Ruta Nord",
  explainerLower: "Ruta Sud",
  explainerCut: "Scurtătura",
  explainerParadox: "Paradox! Scurtătura încetinește pe toată lumea.",
  explainerNoParadox: "Fără paradox la această cerere.",
  explainerNote: "Exemplu clasic de manual, nu date din Timișoara.",
};

export type Dict = typeof ro;

const en: Dict = {
  appName: "TM-BraessGreen",
  subtitle: "Simulator on a real corridor",
  peak: "morning peak",
  explain: "What is Braess's paradox?",
  language: "Language",
  loading: "Loading the network…",
  backendDown: "Can't reach the API. Start the backend (uvicorn) and reload the page.",
  retry: "Retry",

  dataTitle: "Field data",
  dataReady: "Traffic counts are loaded",
  dataMissing: "Results appear once traffic counts are loaded",
  dataMissingBody:
    "The model uses the real OpenStreetMap network but never invents traffic. Fill in the CSV files in backend/data/corridor/ and reload.",
  gatesCounted: "gates counted",
  required: "required",
  optional: "optional",
  filePurpose: {
    "gate_counts.csv": "Cars entering (in) and leaving (out) the area at every gate, morning peak hour. Without these the model has no real demand and shows no results.",
    "turn_counts.csv": "Left/straight/right counts at 2–3 key intersections. Used only to check the model (GEH).",
    "signal_timings.csv": "Cycle and green time per approach (a stopwatch on video is fine). Otherwise a textbook default is used and labelled as an assumption.",
    "lane_checks.csv": "Car lanes verified on site / Street View where OpenStreetMap is wrong or unsure.",
    "travel_times.csv": "GPS travel times along the corridor and its alternative. Used only to check the model.",
  },
  showGates: "Where do we need to count?",
  gatesHint: "Each gate: cars entering (in) and leaving (out), 07:30–08:30, in 15-min intervals.",
  inLabel: "in",
  outLabel: "out",
  openMap: "map",

  step1: "1. Pick a street",
  chooseStreet: "Choose a street in the area…",
  orClickMap: "or click a street on the map",
  direction: "Direction",
  heading: { N: "northbound", NE: "north-east", E: "eastbound", SE: "south-east", S: "southbound", SW: "south-west", W: "westbound", NW: "north-west" },
  segments: "segments",
  carLanesNow: "car lanes now",
  fromOsm: "from OpenStreetMap",
  fieldCheck: "checked on site",
  existingBusLane: "already has a bus lane",

  step2: "2. Change the lanes",
  carLanesAfter: "Car lanes after",
  removedBecomes: "The freed lane becomes",
  uses: { bus: "Bus lane", bike: "Bike lane", sidewalk: "Sidewalk / trees", closed: "Closed to cars" },
  closedForCars: "The street closes to cars",
  run: "Run simulation",
  running: "Calculating…",
  noChange: "Choose fewer car lanes to make a change.",

  step3: "3. Results",
  needsDataResults: "Without traffic counts we show no results — any number would be made up.",
  totalTime: "Total time spent in traffic in the area",
  cars: "Cars — time on the main routes",
  buses: "STPT buses on this corridor",
  busesPerHour: "buses/hour",
  noBuses: "No STPT line uses the changed street.",
  shifts: "Where the traffic goes",
  noShifts: "Traffic doesn't shift noticeably (under 20 veh/h).",
  intersections: "Waiting at intersections",
  vehH: "veh/h",
  min: "min",
  s: "s",
  sensitivity: "Check robustness (demand ±20%)",
  sensitivityTitle: "If real demand is 20% lower / higher",
  demand: "Demand",
  total: "Total",
  mainRoute: "Main route",
  bus: "Bus",

  assumptionsTitle: "Assumptions in use (until we have data)",
  calibrationTitle: "Check: model vs. reality",
  calibrationMissing: "Add turn_counts.csv (turning counts) and travel_times.csv to check the model.",
  gehHint: "GEH < 5 = good match (traffic engineering standard)",
  counted: "counted",
  model: "model",
  observed: "observed",

  sources: "Sources",
  network: "Network",
  legendFlow: "Width = traffic",
  legendLess: "less traffic",
  legendMore: "more traffic",
  legendSelected: "selected street",
  legendGateOk: "gate counted",
  legendGateMissing: "gate without data",
  legendSignal: "traffic light",
  close: "Close",

  explainerIntro:
    "Every driver picks the route that is fastest for them alone. Sometimes a shortcut attracts so many drivers that everyone arrives later. Close the shortcut and the area moves faster!",
  explainerDemand: "Demand (vehicles/hour)",
  explainerShortcut: "Shortcut open",
  explainerTravelTime: "Travel time for every driver",
  explainerTotal: "Total network time",
  explainerUpper: "North route",
  explainerLower: "South route",
  explainerCut: "Shortcut",
  explainerParadox: "Paradox! The shortcut slows everyone down.",
  explainerNoParadox: "No paradox at this demand.",
  explainerNote: "Textbook example, not Timișoara data.",
};

export const translations: Record<Lang, Dict> = { ro, en };

export interface I18nValue {
  lang: Lang;
  t: Dict;
  setLang: (l: Lang) => void;
}

export const I18nContext = createContext<I18nValue>({ lang: "ro", t: ro, setLang: () => undefined });

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
