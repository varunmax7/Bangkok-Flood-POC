"""RGBA colormaps for frame rendering. See docs/VARUN_IMPLEMENTATION.md §6 T40.

Each function maps a 2D float array -> uint8 RGBA array of the same (H, W)
shape; NaN is always transparent.
"""
from __future__ import annotations

import numpy as np


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _binned(arr: np.ndarray, bins: list[float], colors: list[tuple[int, int, int]], alphas: list[int]) -> np.ndarray:
    """colors/alphas[0] is the below-first-bin case (normally transparent)."""
    arr = np.asarray(arr, dtype=np.float64)
    out = np.zeros((*arr.shape, 4), dtype=np.uint8)
    valid = ~np.isnan(arr)
    idx = np.digitize(arr, bins)
    for i, (color, alpha) in enumerate(zip(colors, alphas)):
        mask = valid & (idx == i)
        if mask.any():
            out[mask, 0], out[mask, 1], out[mask, 2], out[mask, 3] = color[0], color[1], color[2], alpha
    return out


# depth_v1: < 0.05 transparent; 0.05-0.15 / 0.15-0.30 / 0.30-0.50 / 0.50-1.0 / >= 1.0
_DEPTH_BINS = [0.05, 0.15, 0.30, 0.50, 1.0]
_DEPTH_COLORS = [(0, 0, 0)] + [_hex_to_rgb(h) for h in ("c6dbef", "6baed6", "2171b5", "08519c", "08306b")]
_DEPTH_ALPHA = [0, 200, 200, 200, 200, 200]


def depth_v1(arr: np.ndarray) -> np.ndarray:
    return _binned(arr, _DEPTH_BINS, _DEPTH_COLORS, _DEPTH_ALPHA)


def extent_v1(arr: np.ndarray) -> np.ndarray:
    """>= 0.10 wet -> solid blue, else transparent."""
    arr = np.asarray(arr, dtype=np.float64)
    out = np.zeros((*arr.shape, 4), dtype=np.uint8)
    wet = (~np.isnan(arr)) & (arr >= 0.10)
    c = _hex_to_rgb("2b8cbe")
    out[wet, 0], out[wet, 1], out[wet, 2], out[wet, 3] = c[0], c[1], c[2], 170
    return out


# sigma_v1: < 0.02 transparent; light -> dark purple at 0.02 / 0.05 / 0.10 / 0.20
# [ASSUMPTION] exact hexes aren't pinned in the spec ("light -> dark purple");
# using ColorBrewer's sequential Purples palette.
_SIGMA_BINS = [0.02, 0.05, 0.10, 0.20]
_SIGMA_COLORS = [(0, 0, 0)] + [_hex_to_rgb(h) for h in ("bcbddc", "9e9ac8", "807dba", "54278f")]
_SIGMA_ALPHA = [0, 200, 200, 200, 200]


def sigma_v1(arr: np.ndarray) -> np.ndarray:
    return _binned(arr, _SIGMA_BINS, _SIGMA_COLORS, _SIGMA_ALPHA)


# error_v1: surrogate - hydraulic; |e| < 0.05 transparent; diverging at
# 0.05/0.15/0.30, red = over-prediction (positive), blue = under (negative).
# [ASSUMPTION] exact hexes aren't pinned; using ColorBrewer Reds/Blues steps.
_ERROR_BINS = [0.05, 0.15, 0.30]
_ERROR_POS_COLORS = [_hex_to_rgb(h) for h in ("fcae91", "fb6a4a", "cb181d")]
_ERROR_NEG_COLORS = [_hex_to_rgb(h) for h in ("bdd7e7", "6baed6", "2171b5")]


def error_v1(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float64)
    out = np.zeros((*arr.shape, 4), dtype=np.uint8)
    valid = ~np.isnan(arr)
    idx = np.digitize(np.abs(arr), _ERROR_BINS)  # 0 (<0.05) .. 3 (>=0.30)
    for level in (1, 2, 3):
        over = valid & (arr > 0) & (idx == level)
        under = valid & (arr < 0) & (idx == level)
        c = _ERROR_POS_COLORS[level - 1]
        out[over, 0], out[over, 1], out[over, 2], out[over, 3] = c[0], c[1], c[2], 200
        c = _ERROR_NEG_COLORS[level - 1]
        out[under, 0], out[under, 1], out[under, 2], out[under, 3] = c[0], c[1], c[2], 200
    return out


def satmask_v1(arr: np.ndarray) -> np.ndarray:
    """Integer-coded satellite flood mask: 1 = wet, 0 = dry (transparent), 255 = nodata."""
    arr = np.asarray(arr)
    out = np.zeros((*arr.shape, 4), dtype=np.uint8)
    wet = arr == 1
    nodata = arr == 255
    c = _hex_to_rgb("e34a33")
    out[wet, 0], out[wet, 1], out[wet, 2], out[wet, 3] = c[0], c[1], c[2], 170
    out[nodata] = (128, 128, 128, 90)
    return out


CMAPS = {
    "depth_v1": depth_v1,
    "extent_v1": extent_v1,
    "sigma_v1": sigma_v1,
    "error_v1": error_v1,
    "satmask_v1": satmask_v1,
}
