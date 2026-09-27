"""MapTilesAdapter interface — MapTiler / OSM. Implemented in Phase 4."""

from __future__ import annotations

from typing import Protocol


class MapTilesAdapter(Protocol):
    def get_tile_url(self) -> str: ...


class OSMTilesAdapter:
    """Free OSM raster tile fallback — used when MAPTILER_API_KEY is absent."""

    def get_tile_url(self) -> str:
        return "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
