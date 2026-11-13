// Mirrors backend/app/models/schemas.py (camelCase aliases) and the /api/network payload.

export type Preset = "morning_rush" | "evening_rush" | "now" | "weekend" | "event_rush";

export type LaneType =
  | "car"
  | "bus"
  | "bike"
  | "pedestrian_trees"
  | "parking_green"
  | "parking_red"
  | "parking_yellow"
  | "parking_blue";

export type LngLat = [number, number];

export interface Feature<G, P> {
  type: "Feature";
  id?: number | string;
  geometry: G;
  properties: P;
}

export interface FeatureCollection<G = Geometry, P = Record<string, unknown>> {
  type: "FeatureCollection";
  features: Feature<G, P>[];
}

export type Geometry =
  | { type: "Point"; coordinates: LngLat }
  | { type: "LineString"; coordinates: LngLat[] }
  | { type: "Polygon"; coordinates: LngLat[][] }
  | { type: "MultiPolygon"; coordinates: LngLat[][][] };

export interface GreenScores {
  bus: number;
  bike: number;
  trees: number;
}

export interface SesizariSummary {
  radiusMeters: number;
  total: number;
  byCategory: Record<string, number>;
  byStatus: Record<string, number>;
  source?: string;
}

export interface RoadProps {
  id: string;
  codGis: string;
  seedCodGis: string;
  codGisSource: string;
  officialName: string | null;
  streetName: string;
  cartier: string;
  direction: string;
  twinId: string | null;
  fromName: string;
  toName: string;
  lengthM: number;
  freeFlowSpeedKmh: number;
  lanes: LaneType[];
  baselineFlow: number;
  capacity: number;
  vOverC: number;
  speedKmh: number;
  travelTimeSec: number;
  bprDelaySec: number;
  braessValueV: number | null;
  braessImprovementPct: number | null;
  prescanMode: "full_closure" | "minus_one_car_lane" | null;
  isBraessCandidate: boolean;
  isGreenOpportunity: boolean;
  greenSuitabilityScores: GreenScores;
  recommendedReallocation: LaneType;
  timparkZone: string | null;
  cyclewayExisting: boolean;
  hotspotId: string | null;
  stptLines: string[];
  sesizariSummary: SesizariSummary;
}

export interface QueueProps {
  id: string;
  intersectionName: string;
  inLinkId: string;
  outLinkId: string;
  control: string;
  flow: number;
  saturationS: number;
  isSaturated: boolean;
  queueDelaySec: number;
  d0Sec: number;
}

export interface Metrics {
  totalSystemDelayVehMin: number;
  braessValueV: number;
  delayReductionPct: number;
  avgIntersectionQueueSec: number;
  co2SavedKgPerHour: number;
  stptRidersBenefitingPerHour: number;
  timparkSpacesDelta: number;
  timparkHourlyRevenueDeltaEur: number;
  co2KgPerHour: number;
  solverIterations: number;
  solverRelativeGap: number;
  solverMs: number;
}

export interface Hotspot {
  id: string;
  rank: number;
  linkId: string;
  codGis: string;
  officialCodGis: string | null;
  name: string;
  streetName: string;
  cartier: string;
  baselineLanes: LaneType[];
  suggestedLanes: LaneType[];
  queueId: string;
  stptLines: string[];
  bikeCorridor: string;
  dataBadge: string;
  center: LngLat;
  zoom: number;
  storyRo: string;
  storyEn: string;
  braessValueV: number;
  delayReductionPct: number;
  queueBeforeSec: number;
  queueAfterSec: number;
  queueFlowBefore: number;
  queueFlowAfter: number;
  saturationS: number;
  linkFlow: number;
  stptRidersBenefitingPerHour: number;
}

export interface ProvenanceEntry {
  dataset: string;
  source: "live" | "cache" | "seed";
  endpoint: string;
  fetchedAt: string | null;
  note: string | null;
}

export interface NetworkResponse {
  preset: Preset;
  roads: FeatureCollection<{ type: "LineString"; coordinates: LngLat[] }, RoadProps>;
  queues: FeatureCollection<{ type: "Point"; coordinates: LngLat }, QueueProps>;
  overlays: {
    zones: FeatureCollection;
    stptLines: FeatureCollection;
    osmCycleways: FeatureCollection;
    iveloStations: FeatureCollection;
    pois: FeatureCollection;
    events: FeatureCollection;
    timparkSegments: FeatureCollection;
    sesizariClusters: FeatureCollection;
    airQuality: FeatureCollection;
  };
  hotspots: Hotspot[];
  baselineMetrics: Metrics;
  odPairs: { id: string; label: string; demandVehH: number }[];
  fiwareSensor: { id: string; name: string; intensity_veh_h_peak: number; dateObserved: string; coordinates: LngLat };
  feedVersion: string;
  timparkTariffsEurH: Record<string, number>;
  fares: { ticketRon: number; dayPassRon: number };
  osm: { attribution: string; badge: string };
  stats: {
    nodes: number;
    roadLinks: number;
    queueLinks: number;
    odPairs: number;
    paths: number;
    braessCandidates: number;
    prescanned: number;
  };
  provenance: ProvenanceEntry[];
}

export interface Intervention {
  linkId: string;
  codGis?: string;
  newLaneAllocation: LaneType[];
  filterCutThroughRoute: boolean;
}

export interface SimulateRequest {
  preset: Preset;
  interventions: Intervention[];
}

export interface UpdatedLink {
  id: string;
  flow: number;
  baselineFlow: number;
  deltaFlow: number;
  capacity: number;
  vOverC: number;
  speedKmh: number;
  travelTimeSec: number;
  bprDelaySec: number;
  lanes: LaneType[];
}

export interface UpdatedQueue {
  id: string;
  intersectionName: string;
  flow: number;
  baselineFlow: number;
  saturationS: number;
  baselineSaturationS: number;
  isSaturated: boolean;
  wasSaturated: boolean;
  queueDelaySec: number;
  baselineQueueDelaySec: number;
  d0Sec: number;
}

export type CarRole = "recommended_arterial" | "throttled_braess_cut_through";

export interface CarRoute {
  id: string;
  name: string;
  odLabel: string;
  role: CarRole;
  oldTimeMin: number;
  newTimeMin: number;
  timeSavedMin: number;
  flowSharePct: number;
  oldFlowSharePct: number;
  deltaFlowVehH: number;
  filteredFromNavigation: boolean;
  coordinates: LngLat[];
}

export interface Stop {
  stopId: string;
  name: string;
  coordinates: LngLat;
}

export interface StptRoute {
  routeId: string;
  shortName: string;
  type: number;
  color: string;
  headsign: string;
  longName: string | null;
  oldCorridorTimeMin: number;
  newCorridorTimeMin: number;
  frequencyPerHour: number;
  nextDepartures: string[];
  departuresSource: string;
  ticketCostRon: number;
  usesEditedStreet: boolean;
  coordinates: LngLat[];
  geometrySource: string;
  stops: Stop[];
}

export interface BikeRoute {
  routeId: string;
  name: string;
  origin: string;
  destination: string;
  lengthKm: number;
  timeMin: number;
  oldTimeMin: number;
  protectedPctBefore: number;
  protectedPctAfter: number;
  iveloStationsOnRoute: string[];
  distanceToEditedStreetM: number;
  coordinates: LngLat[];
}

export interface CostComparison {
  stptTicketRon: number;
  stptDayPassRon: number;
  timparkZone: string | null;
  timparkEurPerHour: number | null;
  timparkRonTwoHours: number | null;
  smsNumber: string;
}

export interface QueueChart {
  queueId: string;
  intersectionName: string;
  d0Sec: number;
  saturationSBefore: number;
  saturationSAfter: number;
  alphaSecPerVehH: number;
  flowBefore: number;
  flowAfter: number;
  curveBefore: [number, number][];
  curveAfter: [number, number][];
}

export interface BprChart {
  linkId: string;
  t0Sec: number;
  capacityBefore: number;
  capacityAfter: number;
  flowBefore: number;
  flowAfter: number;
  curveBefore: [number, number][];
  curveAfter: [number, number][];
}

export interface SimulateResponse {
  preset: Preset;
  baselineMetrics: Metrics;
  simulatedMetrics: Metrics;
  updatedLinks: UpdatedLink[];
  updatedQueues: UpdatedQueue[];
  recommendedRoutes: {
    carRoutes: CarRoute[];
    stptRoutes: StptRoute[];
    bikeRoutes: BikeRoute[];
  };
  costComparison: CostComparison;
  queueChart: QueueChart | null;
  bprChart: BprChart | null;
  sesizariSummary: SesizariSummary | null;
  removedRouteIds: string[];
  closedLinkIds: string[];
  provenance: ProvenanceEntry[];
}

export interface DecidemBriefResponse {
  titleRo: string;
  titleEn: string;
  briefRo: string;
  briefEn: string;
  decidemUrl: string;
  sesizariUrl: string;
  codGis: string[];
  owners: string[];
  metrics: Metrics;
}

export interface HealthResponse {
  status: string;
  version: string;
  feedVersion: string;
  offlineMode: boolean;
  cache: Record<string, ProvenanceEntry>;
  solver: Record<string, unknown>;
}

export interface StreetSearchResult {
  codGis: string;
  denumireCompleta: string;
  denumireCompletaFaraDiacritice: string;
  tipStrada: string | null;
  cartier: string | null;
  linkId: string | null;
  center?: LngLat;
}

/** A highlighted route on the map (hover / click in RecommendedRoutesTabs). */
export interface HighlightedRoute {
  id: string;
  kind: "car_arterial" | "car_cut_through" | "stpt" | "bike";
  color: string;
  coordinates: LngLat[];
  label: string;
  timeLabel: string;
}

export type ColorMode = "absolute" | "delta";

export interface LayerState {
  traffic: boolean;
  braess: boolean;
  flowAnimation: boolean;
  queues: boolean;
  stpt: boolean;
  cycling: boolean;
  timpark: boolean;
  zones: boolean;
  sesizari: boolean;
  pois: boolean;
  airQuality: boolean;
}
