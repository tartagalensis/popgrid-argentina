"""Construcción de mapas de bloques con popgrid.

Cada bloque representa una fracción fija del total (con n=1000, el 0,1%).
Como en cada censo cambia el total, los mapas de distintos años muestran
cómo cambió el *peso relativo* de cada región, no su población absoluta.

Cada censo se dibuja con las regiones que existían en ese momento: una fila
compuesta del CSV (p. ej. Orán + San Martín hasta 1947) se dibuja como la unión
de sus departamentos actuales, y una región sin dato (p. ej. Los Andes antes de
pertenecer a Salta) no se dibuja. Los colores se fijan una sola vez a partir de
las regiones actuales, así cada región conserva su color en todos los censos.
"""

from __future__ import annotations

import math
from functools import cache

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from popgrid import AreaGrid, PopGrid

from . import config
from .censos import cargar_censo, censos_disponibles, partes
from .limites import cargar_limites

TITULOS = {"provincias": "Argentina", "salta": "Salta"}
UNIDAD = {"provincias": "del país", "salta": "de la provincia"}
FUENTES = {
    "provincias": "Límites: IGN · Población: INDEC, censos nacionales · popgrid",
    "salta": "Límites: IGN · Población: INDEC, censos nacionales (serie de la DGE Salta) · popgrid",
}
NOMBRES = {"provincias": config.PROVINCIAS, "salta": config.DEPARTAMENTOS_SALTA}


def _pct(n: int) -> str:
    """Porcentaje que representa un bloque, con coma decimal (0,1)."""
    return f"{100 / n:g}".replace(".", ",")


def _etiquetas(gdf: gpd.GeoDataFrame) -> dict[str, str]:
    return {n: config.ETIQUETAS[n] for n in gdf["nombre"] if n in config.ETIQUETAS}


def _limites(nivel: str) -> gpd.GeoDataFrame:
    limites = cargar_limites(nivel)
    limites["nombre"] = limites["codigo"].map(NOMBRES[nivel])
    if limites["nombre"].isna().any():
        raise ValueError(f"Hay límites con códigos que no están en config ({nivel}).")
    return limites


def regiones_censo(limites: gpd.GeoDataFrame, censo: pd.DataFrame, anio: int) -> gpd.GeoDataFrame:
    """Regiones de un censo con su población: une geometrías de filas compuestas
    y omite las regiones sin dato."""
    geom = limites.set_index("codigo").geometry
    col = f"pob_{anio}"
    filas = censo[censo[col].notna()]
    return gpd.GeoDataFrame(
        {
            "codigo": filas["codigo"].to_list(),
            "nombre": filas["nombre"].to_list(),
            col: filas[col].astype(float).to_list(),
        },
        geometry=[geom.loc[partes(c)].union_all() for c in filas["codigo"]],
        crs=limites.crs,
    )


@cache
def _colores(nivel: str, n: int) -> dict[str, str]:
    """{nombre: color}: colores de las regiones actuales, más el de cada fila
    compuesta (toma el de su primera parte)."""
    limites = _limites(nivel)
    base = AreaGrid.from_geodataframe(limites, region_col="nombre", n=n).color_map
    por_codigo = dict(zip(limites["codigo"], limites["nombre"], strict=True))
    colores = dict(base)
    for _, fila in cargar_censo(nivel).iterrows():
        codigo = fila["codigo"]
        if config.SEPARADOR_COMPUESTO in codigo:
            colores[fila["nombre"]] = base[por_codigo[partes(codigo)[0]]]
    return colores


def nota_censo(regiones: gpd.GeoDataFrame, nivel: str) -> str:
    """Aclaración para censos en que las regiones no son las actuales."""
    notas = []
    compuestas = regiones[regiones["codigo"].str.contains(config.SEPARADOR_COMPUESTO, regex=False)]
    notas += [f"{n} figuran juntos" for n in compuestas["nombre"]]
    cubiertos = {p for c in regiones["codigo"] for p in partes(c)}
    faltan = sorted(set(NOMBRES[nivel]) - cubiertos)
    if faltan:
        nombres = ", ".join(NOMBRES[nivel][c] for c in faltan)
        notas.append(
            f"sin {nombres} (aún no integraba{'n' if len(faltan) > 1 else ''} {TITULOS[nivel]})"
        )
    return "; ".join(notas)


def grilla_superficie(nivel: str, n: int = 1000) -> AreaGrid:
    limites = _limites(nivel)
    colores = _colores(nivel, n)
    return AreaGrid.from_geodataframe(
        limites,
        region_col="nombre",
        n=n,
        color_map={r: colores[r] for r in limites["nombre"]},
    )


def _rango_censos(anios: list[int], todos: list[int]) -> str:
    """'1869 a 1947' si son censos consecutivos de la serie; si no, '1869, 1914'."""
    i = todos.index(anios[0])
    if len(anios) > 2 and todos[i : i + len(anios)] == anios:
        return f"{anios[0]} a {anios[-1]}"
    return " y ".join(", ".join(map(str, anios)).rsplit(", ", 1))


def grilla_poblacion(nivel: str, anio: int, n: int = 1000) -> tuple[PopGrid, gpd.GeoDataFrame]:
    censo = cargar_censo(nivel)
    if anio not in censos_disponibles(censo):
        raise ValueError(f"El censo {anio} no está completo para '{nivel}'.")
    regiones = regiones_censo(_limites(nivel), censo, anio)
    colores = _colores(nivel, n)
    grilla = PopGrid.from_geodataframe(
        regiones,
        region_col="nombre",
        weight_col=f"pob_{anio}",
        n=n,
        color_map={r: colores[r] for r in regiones["nombre"] if r in colores},
    )
    return grilla, regiones


def mapa_superficie(nivel: str, n: int = 1000) -> Figure:
    return grilla_superficie(nivel, n).plot(
        title=f"Superficie de {TITULOS[nivel]}",
        subtitle=f"Cada bloque = {_pct(n)}% de la superficie {UNIDAD[nivel]}",
        data_source="Límites: IGN · popgrid",
        labels=_etiquetas(_limites(nivel)),
    )


def mapa_poblacion(nivel: str, anio: int, n: int = 1000) -> Figure:
    grilla, regiones = grilla_poblacion(nivel, anio, n)
    nota = nota_censo(regiones, nivel)
    return grilla.plot(
        title=f"Población de {TITULOS[nivel]} · Censo {anio}",
        subtitle=f"Cada bloque = {_pct(n)}% de la población {UNIDAD[nivel]}",
        data_source=f"{nota[0].upper()}{nota[1:]} · {FUENTES[nivel]}" if nota else FUENTES[nivel],
        labels=_etiquetas(regiones),
    )


def comparar_censos(
    nivel: str,
    censos: list[int] | None = None,
    n: int = 1000,
    incluir_superficie: bool = True,
    columnas: int = 4,
) -> Figure:
    """Grilla de mapas: superficie (opcional) + un mapa por censo."""
    censos = censos or censos_disponibles(cargar_censo(nivel))
    if not censos:
        raise ValueError("No hay ningún censo completo cargado en data/censos/.")

    paneles: list[tuple[str, AreaGrid | PopGrid, dict[str, str]]] = []
    if incluir_superficie:
        paneles.append(("Superficie", grilla_superficie(nivel, n), _etiquetas(_limites(nivel))))
    anios_por_nota: dict[str, list[int]] = {}
    for anio in censos:
        grilla, regiones = grilla_poblacion(nivel, anio, n)
        paneles.append((f"Censo {anio}", grilla, _etiquetas(regiones)))
        for parte in filter(None, nota_censo(regiones, nivel).split("; ")):
            anios_por_nota.setdefault(parte, []).append(anio)
    notas = [f"{_rango_censos(a, list(censos))}: {nota}" for nota, a in anios_por_nota.items()]

    # Alto de cada panel según la proporción real del territorio (Argentina es
    # alta y angosta, Salta más ancha), para no dejar franjas vacías.
    xmin, ymin, xmax, ymax = _limites(nivel).to_crs(config.CRS_METRICO).total_bounds
    ncols = min(columnas, len(paneles))
    nfilas = math.ceil(len(paneles) / ncols)
    ancho_panel = 4.5
    alto_panel = ancho_panel * min(max((ymax - ymin) / (xmax - xmin), 0.6), 2.2)
    pie = 0.45 + 0.22 * len(notas)
    alto = alto_panel * nfilas + 0.95 + pie
    fig, ejes = plt.subplots(nfilas, ncols, figsize=(ancho_panel * ncols, alto), squeeze=False)
    fig.subplots_adjust(
        left=0.01, right=0.99, top=1 - 0.95 / alto, bottom=pie / alto, wspace=0.04, hspace=0.12
    )
    ejes = list(ejes.flat)
    for ax, (titulo, grilla, etiquetas) in zip(ejes, paneles, strict=False):
        grilla.draw(ax, background_style="none", labels=etiquetas)
        ax.set_title(titulo, fontsize=14, fontweight="bold")
    for ax in ejes[len(paneles) :]:
        ax.set_axis_off()

    fig.suptitle(
        f"{TITULOS[nivel]}: superficie y población por censo",
        fontsize=18,
        fontweight="bold",
        y=1 - 0.2 / alto,
    )
    pie_texto = [f"Cada bloque = {_pct(n)}% del total · {FUENTES[nivel]}"] + notas
    fig.text(0.5, 0.12 / alto, "\n".join(pie_texto), ha="center", va="bottom", fontsize=9)
    return fig
