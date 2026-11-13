"""Strict Pydantic v2 request/response contracts (mirrored in frontend/src/types/simulator.ts)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Preset = Literal["morning_rush", "evening_rush", "now", "weekend", "event_rush"]
LaneType = Literal[
    "car", "bus", "bike", "pedestrian_trees",
    "parking_green", "parking_red", "parking_yellow", "parking_blue",
]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class FeatureCollection(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class Intervention(CamelModel):
    link_id: str = Field(..., examples=["LINK_CLUJ_01"])
    cod_gis: str | None = Field(None, examples=["1042"])
    new_lane_allocation: list[LaneType] = Field(..., min_length=1, max_length=6)
    filter_cut_through_route: bool = False


class SimulateRequest(CamelModel):
    preset: Preset = "morning_rush"
    interventions: list[Intervention] = Field(default_factory=list, max_length=8)

    @field_validator("interventions")
    @classmethod
    def unique_links(cls, v: list[Intervention]) -> list[Intervention]:
        ids = [i.link_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("each linkId may appear only once")
        return v


class DecidemBriefRequest(SimulateRequest):
    hotspot_id: str | None = None
    language: Literal["ro", "en", "both"] = "both"


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class Metrics(CamelModel):
    total_system_delay_veh_min: float
    braess_value_v: float
    delay_reduction_pct: float
    avg_intersection_queue_sec: float
    co2_saved_kg_per_hour: float
    stpt_riders_benefiting_per_hour: int
    timpark_spaces_delta: int
    timpark_hourly_revenue_delta_eur: float
    co2_kg_per_hour: float
    solver_iterations: int
    solver_relative_gap: float
    solver_ms: float


class UpdatedLink(CamelModel):
    id: str
    flow: float
    baseline_flow: float
    delta_flow: float
    capacity: float
    v_over_c: float
    speed_kmh: float
    travel_time_sec: float
    bpr_delay_sec: float
    lanes: list[str]


class UpdatedQueue(CamelModel):
    id: str
    intersection_name: str
    flow: float
    baseline_flow: float
    saturation_s: float
    baseline_saturation_s: float
    is_saturated: bool
    was_saturated: bool
    queue_delay_sec: float
    baseline_queue_delay_sec: float
    d0_sec: float


class CarRoute(CamelModel):
    id: str
    name: str
    od_label: str
    role: Literal["recommended_arterial", "throttled_braess_cut_through"]
    old_time_min: float
    new_time_min: float
    time_saved_min: float
    flow_share_pct: float
    old_flow_share_pct: float
    delta_flow_veh_h: float
    filtered_from_navigation: bool
    coordinates: list[list[float]]


class Stop(CamelModel):
    stop_id: str
    name: str
    coordinates: list[float]


class StptRoute(CamelModel):
    route_id: str
    short_name: str
    type: int
    color: str
    headsign: str
    long_name: str | None = None
    old_corridor_time_min: float
    new_corridor_time_min: float
    frequency_per_hour: float
    next_departures: list[str]
    departures_source: str
    ticket_cost_ron: float
    uses_edited_street: bool
    coordinates: list[list[float]]
    geometry_source: str
    stops: list[Stop]


class BikeRoute(CamelModel):
    route_id: str
    name: str
    origin: str
    destination: str
    length_km: float
    time_min: float
    old_time_min: float
    protected_pct_before: float
    protected_pct_after: float
    ivelo_stations_on_route: list[str]
    distance_to_edited_street_m: float
    coordinates: list[list[float]]


class RecommendedRoutes(CamelModel):
    car_routes: list[CarRoute]
    stpt_routes: list[StptRoute]
    bike_routes: list[BikeRoute]


class CostComparison(CamelModel):
    stpt_ticket_ron: float
    stpt_day_pass_ron: float
    timpark_zone: str | None
    timpark_eur_per_hour: float | None
    timpark_ron_two_hours: float | None
    sms_number: str


class QueueChart(CamelModel):
    """Φ_q(z) curve samples for the 'Braess proof' chart."""
    queue_id: str
    intersection_name: str
    d0_sec: float
    saturation_s_before: float
    saturation_s_after: float
    alpha_sec_per_veh_h: float
    flow_before: float
    flow_after: float
    curve_before: list[list[float]]
    curve_after: list[list[float]]


class BprChart(CamelModel):
    link_id: str
    t0_sec: float
    capacity_before: float
    capacity_after: float
    flow_before: float
    flow_after: float
    curve_before: list[list[float]]
    curve_after: list[list[float]]


class SimulateResponse(CamelModel):
    preset: Preset
    baseline_metrics: Metrics
    simulated_metrics: Metrics
    updated_links: list[UpdatedLink]
    updated_queues: list[UpdatedQueue]
    recommended_routes: RecommendedRoutes
    cost_comparison: CostComparison
    queue_chart: QueueChart | None
    bpr_chart: BprChart | None
    sesizari_summary: dict[str, Any] | None
    removed_route_ids: list[str]
    closed_link_ids: list[str]
    provenance: list[dict[str, Any]]


class DecidemBriefResponse(CamelModel):
    title_ro: str
    title_en: str
    brief_ro: str
    brief_en: str
    decidem_url: str
    sesizari_url: str
    cod_gis: list[str]
    owners: list[str]
    metrics: Metrics


class HealthResponse(CamelModel):
    status: str
    version: str
    feed_version: str
    offline_mode: bool
    cache: dict[str, Any]
    solver: dict[str, Any]
