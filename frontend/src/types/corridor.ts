// Mirrors backend/app/corridor/api.py

export type LngLat = [number, number];
export type LaneUse = "bus" | "bike" | "sidewalk" | "closed";
export type Profile = "morning" | "day" | "evening" | "sunday";
/** "estimated" = demand from OSM land use only; "calibrated" = field counts loaded for that profile. */
export type DemandSource = "estimated" | "calibrated";

export interface ProfileMeta {
  id: Profile;
  labelRo: string;
  labelEn: string;
  start: string;
  end: string;
  day: "weekday" | "sunday";
}

export interface DemandSummary {
  residents: number;
  homeTripsVehH: number;
  localTripsVehH: number;
  gatewayInVehH: number;
  gatewayOutVehH: number;
  throughVehH: number;
  totalVehH: number;
  localMultiplier: number;
  countedGates: string[];
}

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
  roadClass: string;
  isSideStreet: boolean;
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
  countedProfiles: Profile[];
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

export interface ProfileDataStatus {
  calibrated: boolean;
  gatesCounted: number;
  linkCounts: number;
  turnCounts: number;
  travelTimes: number;
}

export interface DataStatus {
  ready: boolean;
  demandSource: DemandSource;
  profiles: Record<Profile, ProfileDataStatus>;
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

export interface ZoneProps {
  id: string;
  label: string;
  residents: number;
  activity: Record<string, number>;
}

export interface LandUseSummary {
  buildings: number;
  residentialBuildings: number;
  levelsFromOsm: number;
  residents: number;
  pois: number;
  untypedBuildings: number;
  zones: number;
  activityByCategory: Record<string, number>;
  carShare: number;
  carShareVerified: boolean;
}

export interface CorridorResponse {
  corridor: { id: string; name: string; bbox: number[]; mainStreets: string[]; peak: string };
  profiles: ProfileMeta[];
  defaultProfile: Profile;
  zones: FC<{ type: "Point"; coordinates: LngLat }, ZoneProps>;
  landUse: LandUseSummary;
  links: FC<{ type: "LineString"; coordinates: LngLat[] }, LinkProps>;
  gates: FC<{ type: "Point"; coordinates: LngLat }, GateProps>;
  junctions: FC<{ type: "Point"; coordinates: LngLat }, JunctionProps>;
  streets: StreetChoice[];
  dataStatus: DataStatus;
  assumptions: Assumption[];
  sources: {
    network: string;
    networkFetchedAt: string;
    stats: { links: number; junctions: number; signalized: number; gates: number; sideStreetLinks: number; zones: number };
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
  profile: Profile;
  demandSource: DemandSource;
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
  braess: boolean;
  mainRoute: { name: string; minutesBefore: number; minutesAfter: number } | null;
  bus: { shortName: string; minutesBefore: number; minutesAfter: number } | null;
}

export type SensitivityResponse = { status: "ok"; profile: Profile; demandSource: DemandSource; rows: SensitivityRow[] } | NeedsData;

export interface FittedRow {
  street: string;
  counted: number;
  model: number;
  geh: number;
}

export interface CalibrationOk {
  status: "ok";
  profile: Profile;
  demandSource: DemandSource;
  localMultiplier: number;
  fitted: {
    gates: (FittedRow & { gateId: string; direction: "in" | "out" })[];
    links: (FittedRow & { linkId: string })[];
    note: string;
  };
  turns: { nodeId: string; intersection: string; from: string; to: string; counted: number; model: number; geh: number }[];
  travelTimes: { route: string; observedMin: number; modelMin: number; diffPct: number }[];
  summary: { turnsCounted: number; gehUnder5: number; gehUnder5Pct: number | null; travelTimesChecked: number; target: string };
}

export type CalibrationResponse = CalibrationOk | NeedsData;

export interface BaselineLink {
  id: string;
  flow: number;
  timeSec: number;
  freeTimeSec: number;
}

export type BaselineResponse =
  | {
      status: "ok";
      profile: Profile;
      demandSource: DemandSource;
      demandSummary: DemandSummary;
      totalVehMin: number;
      links: BaselineLink[];
      junctions: { nodeId: string; delaySec: number }[];
    }
  | NeedsData;

/** UI lane type in the mixer. */
export type LaneKind = "car" | "bus" | "bike" | "sidewalk";

export interface Pin {
  street: string;
  heading: string;
}

/** One tested change from the Braess search.
 *  kind "removal": one street segment closed to cars in BOTH directions (linkIds = both directions).
 *  kind "lane":    one car lane taken from every multi-lane link of a street direction. */
export interface ScanRow {
  street: string;
  heading: string;
  linkIds: string[];
  mode: "minus_one_lane" | "closure";
  kind: "removal" | "lane";
  scope: "both" | "one";
  fromName: string;
  toName: string;
  changePct: number;
  vehMinDelta: number;
  vehHSaved: number;
  braess: boolean;
  routeBraess: boolean;
  bestRouteGainPct: number;
  lowRegret: boolean;
  stage: "quick" | "verified";
  baseFlow: number;
  at: LngLat;
}

export type ScanResponse =
  | {
      status: "ok";
      profile: Profile;
      demandSource: DemandSource;
      rows: ScanRow[];
      braessCount: number;
      routeBraessCount: number;
      lowRegretCount: number;
      tested: { removal: number; lane: number; verified: number; skippedDisconnecting: number };
      seconds: number;
    }
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
