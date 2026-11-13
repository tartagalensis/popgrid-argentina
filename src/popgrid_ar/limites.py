"""Descarga y preparación de límites geográficos desde el IGN.

Flujo:
    1. `descargar_departamentos()` baja la capa completa de departamentos del
       WFS del IGN a data/raw/ (~140 MB, se hace una sola vez).
    2. `construir_limites()` genera versiones simplificadas y livianas en
       data/limites/ (estas sí se versionan en git):
         - provincias.geojson         24 jurisdicciones (dissolve de departamentos)
         - salta_departamentos.geojson 23 departamentos de Salta
         - departamentos.geojson       todos los departamentos del país
    3. `cargar_limites(nivel)` lee esas versiones para armar los mapas.
"""

from __future__ import annotations

import os
from pathlib import Path

# Algunos departamentos del IGN (p. ej. costas e islas) superan el límite por
# objeto de GDAL para GeoJSON (200 MB por defecto); 0 = sin límite.
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")

import geopandas as gpd  # noqa: E402
import requests

from . import config

ARCHIVO_CRUDO = config.CRUDOS / "ign_departamentos.geojson"
ARCHIVOS = {
    "provincias": config.LIMITES / "provincias.geojson",
    "salta": config.LIMITES / "salta_departamentos.geojson",
    "departamentos": config.LIMITES / "departamentos.geojson",
}


def descargar_departamentos(destino: Path = ARCHIVO_CRUDO, forzar: bool = False) -> Path:
    """Descarga todos los departamentos del país desde el WFS del IGN."""
    if destino.exists() and not forzar:
        print(f"Ya existe {destino}, no se descarga (usá forzar=True para rehacerlo).")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": config.IGN_CAPA_DEPARTAMENTOS,
        "outputFormat": "application/json",
        "propertyName": "in1,nam,geom",
    }
    temporal = destino.with_suffix(".parcial")
    with requests.get(config.IGN_WFS, params=params, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(temporal, "wb") as f:
            for bloque in r.iter_content(chunk_size=1 << 20):
                f.write(bloque)
    temporal.replace(destino)
    print(f"Descargado {destino} ({destino.stat().st_size / 1e6:.0f} MB)")
    return destino


def _leer_crudo(origen: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(origen)
    gdf = gdf.rename(columns={"in1": "codigo", "nam": "nombre"})[["codigo", "nombre", "geometry"]]
    gdf["codigo"] = gdf["codigo"].astype(str).str.zfill(5)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf[~gdf["codigo"].isin(config.DEPARTAMENTOS_EXCLUIDOS)]
    gdf = gdf.to_crs(config.CRS_METRICO)
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def _simplificar(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(
        config.TOLERANCIA_SIMPLIFICACION_M, preserve_topology=True
    )
    return gdf.to_crs("EPSG:4326")


def construir_limites(origen: Path = ARCHIVO_CRUDO) -> dict[str, Path]:
    """Genera los GeoJSON livianos de provincias y de departamentos de Salta."""
    if not origen.exists():
        raise FileNotFoundError(
            f"No existe {origen}. Corré primero: python scripts/descargar_limites.py"
        )
    deptos = _leer_crudo(origen)
    config.LIMITES.mkdir(parents=True, exist_ok=True)

    # Provincias: se disuelven los departamentos ANTES de simplificar para
    # que no queden huecos entre departamentos vecinos.
    deptos["provincia"] = deptos["codigo"].str[:2]
    provincias = deptos.dissolve(by="provincia", as_index=False)[["provincia", "geometry"]]
    provincias = provincias.rename(columns={"provincia": "codigo"})
    provincias["nombre"] = provincias["codigo"].map(config.PROVINCIAS)
    faltantes = set(config.PROVINCIAS) - set(provincias["codigo"])
    if faltantes:
        raise ValueError(f"Faltan provincias en la descarga del IGN: {sorted(faltantes)}")
    _simplificar(provincias[["codigo", "nombre", "geometry"]]).to_file(
        ARCHIVOS["provincias"], driver="GeoJSON"
    )

    salta = deptos[deptos["codigo"].str.startswith(config.CODIGO_SALTA)]
    if set(salta["codigo"]) != set(config.DEPARTAMENTOS_SALTA):
        raise ValueError("Los departamentos de Salta del IGN no coinciden con config.py")
    _simplificar(salta[["codigo", "nombre", "geometry"]]).to_file(
        ARCHIVOS["salta"], driver="GeoJSON"
    )

    # Todos los departamentos del país (para trabajar otras provincias).
    _simplificar(deptos[["codigo", "nombre", "geometry"]]).to_file(
        ARCHIVOS["departamentos"], driver="GeoJSON"
    )

    for nivel, ruta in ARCHIVOS.items():
        print(f"{nivel}: {ruta} ({ruta.stat().st_size / 1e6:.1f} MB)")
    return ARCHIVOS


def cargar_limites(nivel: str) -> gpd.GeoDataFrame:
    """Lee los límites simplificados de `nivel` ('provincias', 'salta' o 'departamentos')."""
    if nivel not in ARCHIVOS:
        raise ValueError(f"Nivel desconocido {nivel!r}; opciones: {sorted(ARCHIVOS)}")
    ruta = ARCHIVOS[nivel]
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}. Corré: python scripts/descargar_limites.py")
    gdf = gpd.read_file(ruta)
    gdf["codigo"] = gdf["codigo"].astype(str).str.zfill(2 if nivel == "provincias" else 5)
    return gdf
