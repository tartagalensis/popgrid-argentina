"""Construcción de mapas de bloques con popgrid.

Cada bloque representa una fracción fija del total (con n=1000, el 0,1%).
Como en cada censo cambia el total, los mapas de distintos años muestran
cómo cambió el *peso relativo* de cada región, no su población absoluta.
"""

from __future__ import annotations

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from popgrid import AreaGrid, PopGrid

from . import config
from .censos import cargar_censo, censos_disponibles
from .limites import cargar_limites

FUENTE = "Límites: IGN · Población: INDEC, censos nacionales · popgrid"
TITULOS = {"provincias": "Argentina", "salta": "Salta"}
UNIDAD = {"provincias": "del país", "salta": "de la provincia"}


def preparar(nivel: str) -> tuple[gpd.GeoDataFrame, list[int]]:
    """Une límites y censos por código INDEC. Devuelve el GeoDataFrame y los
    censos completos disponibles."""
    limites = cargar_limites(nivel)
    censo = cargar_censo(nivel)
    gdf = limites.merge(censo.drop(columns="nombre"), on="codigo", how="inner", validate="1:1")
    if len(gdf) != len(limites):
        raise ValueError(f"No coinciden todos los códigos entre límites y censo ({nivel}).")
    gdf["nombre"] = gdf["codigo"].map(
        config.PROVINCIAS if nivel == "provincias" else config.DEPARTAMENTOS_SALTA
    )
    return gdf, censos_disponibles(censo)


def _pct(n: int) -> str:
    """Porcentaje que representa un bloque, con coma decimal (0,1)."""
    return f"{100 / n:g}".replace(".", ",")


def _etiquetas(gdf: gpd.GeoDataFrame) -> dict[str, str]:
    return {n: config.ETIQUETAS[n] for n in gdf["nombre"] if n in config.ETIQUETAS}


def grilla_superficie(gdf: gpd.GeoDataFrame, n: int = 1000) -> AreaGrid:
    return AreaGrid.from_geodataframe(gdf, region_col="nombre", n=n)


def grilla_poblacion(gdf: gpd.GeoDataFrame, censo: int, n: int = 1000) -> PopGrid:
    columna = f"pob_{censo}"
    if gdf[columna].isna().any():
        raise ValueError(f"El censo {censo} tiene datos faltantes; completá data/censos/.")
    datos = gdf.assign(**{columna: gdf[columna].astype(float)})
    return PopGrid.from_geodataframe(datos, region_col="nombre", weight_col=columna, n=n)


def mapa_superficie(nivel: str, n: int = 1000) -> Figure:
    gdf, _ = preparar(nivel)
    return grilla_superficie(gdf, n).plot(
        title=f"Superficie de {TITULOS[nivel]}",
        subtitle=f"Cada bloque = {_pct(n)}% de la superficie {UNIDAD[nivel]}",
        data_source="Límites: IGN · popgrid",
        labels=_etiquetas(gdf),
    )


def mapa_poblacion(nivel: str, censo: int, n: int = 1000) -> Figure:
    gdf, _ = preparar(nivel)
    return grilla_poblacion(gdf, censo, n).plot(
        title=f"Población de {TITULOS[nivel]} · Censo {censo}",
        subtitle=f"Cada bloque = {_pct(n)}% de la población {UNIDAD[nivel]}",
        data_source=FUENTE,
        labels=_etiquetas(gdf),
    )


def comparar_censos(
    nivel: str, censos: list[int] | None = None, n: int = 1000, incluir_superficie: bool = True
) -> Figure:
    """Una fila de mapas: superficie (opcional) + un mapa por censo."""
    gdf, disponibles = preparar(nivel)
    censos = censos or disponibles
    if not censos:
        raise ValueError("No hay ningún censo completo cargado en data/censos/.")

    paneles: list[tuple[str, AreaGrid | PopGrid]] = []
    if incluir_superficie:
        paneles.append(("Superficie", grilla_superficie(gdf, n)))
    paneles += [(f"Censo {c}", grilla_poblacion(gdf, c, n)) for c in censos]

    # Alto de cada panel según la proporción real del territorio (Argentina es
    # alta y angosta, Salta más ancha), para no dejar franjas vacías.
    xmin, ymin, xmax, ymax = gdf.to_crs(config.CRS_METRICO).total_bounds
    ancho_panel = 4.5
    alto_panel = ancho_panel * min(max((ymax - ymin) / (xmax - xmin), 0.6), 2.2)
    alto = alto_panel + 1.4  # título arriba + fuente abajo (pulgadas)
    fig, ejes = plt.subplots(1, len(paneles), figsize=(ancho_panel * len(paneles), alto))
    fig.subplots_adjust(left=0.01, right=0.99, top=1 - 0.95 / alto, bottom=0.45 / alto, wspace=0.04)
    ejes = [ejes] if len(paneles) == 1 else list(ejes)
    for ax, (titulo, grilla) in zip(ejes, paneles, strict=True):
        grilla.draw(ax, background_style="none", labels=_etiquetas(gdf))
        ax.set_title(titulo, fontsize=14, fontweight="bold")
    fig.suptitle(
        f"{TITULOS[nivel]}: superficie y población por censo",
        fontsize=18,
        fontweight="bold",
        y=1 - 0.2 / alto,
    )
    fig.text(0.5, 0.15 / alto, f"Cada bloque = {_pct(n)}% del total · {FUENTE}", ha="center")
    return fig
