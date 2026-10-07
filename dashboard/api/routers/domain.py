from fastapi import APIRouter, HTTPException

from .. import store

router = APIRouter(prefix="/api", tags=["domain"])


@router.get("/domain")
def get_domain():
    domain, polygon, is_mock = store.load_domain()
    if domain is None:
        raise HTTPException(404, "domain not found; run `make fixtures` or provide configs/domain.yaml")

    geometry = polygon["features"][0]["geometry"] if polygon and polygon.get("features") else None
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "crs": domain.get("crs"),
            "res_m": domain.get("res_m"),
            "shape": domain.get("shape"),
            "is_mock": is_mock,
        },
        # duplicated at top level per the §30.2 contract ("GeoJSON Feature + {crs, res_m, shape}")
        "crs": domain.get("crs"),
        "res_m": domain.get("res_m"),
        "shape": domain.get("shape"),
    }
