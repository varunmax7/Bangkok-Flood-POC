from fastapi import APIRouter, HTTPException

from .. import store

router = APIRouter(prefix="/api", tags=["stations"])


@router.get("/stations")
def list_stations(type: str | None = None):
    fc = store.stations_geojson(type)
    if fc is None:
        return {"type": "FeatureCollection", "features": [], "gap": "No station data available [DATA GAP]"}
    return fc


@router.get("/stations/{station_id}/timeseries")
def station_timeseries(station_id: str, start: str | None = None, end: str | None = None):
    data = store.station_timeseries(station_id, start, end)
    if data is None:
        raise HTTPException(404, f"station not found: {station_id}")
    return data
