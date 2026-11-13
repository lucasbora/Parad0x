// Mirrors backend/app/corridor/api.py

export type LngLat = [number, number];
export type LaneUse = "bus" | "bike" | "sidewalk" | "closed";

export interface LinkProps {
  id: string;
  street: string;
  heading: string;
  lengthM: number;
  carLanes: number;
  lanesSource: string;
  speedKmh: number;
  speedSource: string;
  busLane: boolean;
  isMainStreet: boolean;
  signalAtEnd: boolean;
  signalSource: string | null;
  fromName: string;
  toName: string;
  inside: boolean;
}

export interface GateProps {
  id: string;
  street: string;
  side: "N" | "E" | "S" | "W";
  needsIn: boolean;
  needsOut: boolean;
  countedIn: boolean;
  countedOut: boolean;
  inVehH: number;
  outVehH: number;
  source: string | null;
}

export interface JunctionProps {
  id: string;
  name: string;
  signalized: boolean;
}

export interface FC<G, P> {
  type: "FeatureCollection";
  features: { type: "Feature"; geometry: G; properties: P }[];
}

export interface DataFile {
  file: string;
  present: boolean;
  rows: number;
  required: boolean;
  purpose: string;
}

export interface DataStatus {
  ready: boolean;
  files: DataFile[];
  gatesCounted: number;
  gatesTotal: number;
  warnings: string[];
  inputDir: string;
}

export interface Assumption {
  what: string;
  value: string;
  appliesTo: string;
  replaceWith: string;
}

export interface StreetChoice {
  street: string;
  directions: { heading: string; linkIds: string[] }[];
}

export interface CorridorResponse {
  corridor: { id: string; name: string; bbox: number[]; mainStreets: string[]; peak: string };
  links: FC<{ type: "LineString"; coordinates: LngLat[] }, LinkProps>;
  gates: FC<{ type: "Point"; coordinates: LngLat }, GateProps>;
  junctions: FC<{ type: "Point"; coordinates: LngLat }, JunctionProps>;
  streets: StreetChoice[];
  dataStatus: DataStatus;
  assumptions: Assumption[];
  sources: {
    network: string;
    networkFetchedAt: string;
    stats: { links: number; junctions: number; signalized: number; gates: number };
  };
}

export interface Change {
  linkId: string;
  carLanesAfter: number;
  use: LaneUse;
}

export interface LinkResult {
  id: string;
  flowBefore: number;
  flowAfter: number;
  deltaFlow: number;
  timeBeforeSec: number;
  timeAfterSec: number;
  freeTimeSec: number;
}

export interface CarRoute {
  from: string;
  to: string;
  fromGate: string;
  toGate: string;
  vehH: number;
  minutesBefore: number;
  minutesAfter: number;
  pathBefore: LngLat[];
  pathAfter: LngLat[];
}

export interface TrafficShift {
  street: string;
  heading: string;
  deltaFlow: number;
  flowBefore: number;
  flowAfter: number;
  linkId: string;
}

export interface IntersectionResult {
  nodeId: string;
  name: string;
  signalized: boolean;
  delayBeforeSec: number;
  delayAfterSec: number;
  lng: number;
  lat: number;
}

export interface BusResult {
  shortName: string;
  routeId: string;
  type: number;
  color: string;
  longName: string | null;
  direction: number;
  minutesBefore: number;
  minutesAfter: number;
  usesChangedStreet: boolean;
  busesPerHour: number | null;
  busesPerHourSource: string;
  linkIds: string[];
}

export interface SimulateOk {
  status: "ok";
  testData: boolean;
  braess: { detected: boolean; carCapacityRemoved: boolean; totalChangePct: number };
  totals: { vehMinBefore: number; vehMinAfter: number; changePct: number; demandVehH: number };
  carRoutes: CarRoute[];
  junctions: { nodeId: string; delayBeforeSec: number; delayAfterSec: number }[];
  trafficShifts: TrafficShift[];
  intersections: IntersectionResult[];
  buses: BusResult[];
  links: LinkResult[];
  solver: { gapBefore: number; gapAfter: number; iterationsAfter: number; msAfter: number };
  demandScale: number;
  warnings: string[];
}

export interface NeedsData {
  status: "needs_data";
  dataStatus: DataStatus;
}

export type SimulateResponse = SimulateOk | NeedsData;

export interface SensitivityRow {
  demandScale: number;
  totalChangePct: number;
  mainRoute: { name: string; minutesBefore: number; minutesAfter: number } | null;
  bus: { shortName: string; minutesBefore: number; minutesAfter: number } | null;
}

export type SensitivityResponse = { status: "ok"; rows: SensitivityRow[] } | NeedsData;

export interface CalibrationOk {
  status: "ok";
  turns: { nodeId: string; intersection: string; from: string; to: string; counted: number; model: number; geh: number }[];
  travelTimes: { route: string; observedMin: number; modelMin: number; diffPct: number }[];
  summary: { turnsCounted: number; gehUnder5: number; gehUnder5Pct: number | null; target: string };
}

export type CalibrationResponse = CalibrationOk | NeedsData;

export interface BaselineLink {
  id: string;
  flow: number;
  timeSec: number;
  freeTimeSec: number;
}

export type BaselineResponse =
  | { status: "ok"; testData: boolean; totalVehMin: number; links: BaselineLink[]; junctions: { nodeId: string; delaySec: number }[] }
  | NeedsData;

/** UI lane type in the mixer. */
export type LaneKind = "car" | "bus" | "bike" | "sidewalk";

export interface Pin {
  street: string;
  heading: string;
}

export interface ScanRow {
  street: string;
  heading: string;
  linkIds: string[];
  mode: "minus_one_lane" | "closure";
  changePct: number;
  vehMinDelta: number;
  braess: boolean;
  lowRegret: boolean;
}

export type ScanResponse =
  | { status: "ok"; testData: boolean; rows: ScanRow[]; braessCount: number; lowRegretCount: number }
  | NeedsData;

export interface MapLayers {
  traffic: boolean;
  glow: boolean;
  flow: boolean;
  intersections: boolean;
  gates: boolean;
  buildings3d: boolean;
}

/** A route highlighted on the map with A/B pins and a time callout. */
export interface Highlight {
  coordinates: LngLat[];
  ghost?: LngLat[];          // previous route, drawn dashed
  color: string;
  label: string;
  time: string;
}
