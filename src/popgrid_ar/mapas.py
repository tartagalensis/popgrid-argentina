"""Construcción de mapas de bloques con popgrid.

Cada bloque representa una fracción fija del total (con n=1000, el 0,1%).
Como en cada censo cambia el total, los mapas de distintos años muestran
cómo cambió el *peso relativo* de cada región, no su población absoluta.

Funciona para cualquier nivel (ver popgrid_ar.niveles): provincias,
departamentos de una provincia o zonas (departamentos agrupados).

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
from .censos import cargar_censo, censos_disponibles, columna, es_porcentaje, partes
from .limites import cargar_limites
from .niveles import Nivel, slug, zonas
from .niveles import nivel as obtener_nivel


def _n(nivel: str | Nivel) -> Nivel:
    return nivel if isinstance(nivel, Nivel) else obtener_nivel(nivel)


def _pct(n: int) -> str:
    """Porcentaje que representa un bloque, con coma decimal (0,1)."""
    return f"{100 / n:g}".replace(".", ",")


def _etiquetas(gdf: gpd.GeoDataFrame) -> dict[str, str]:
    return {n: config.ETIQUETAS[n] for n in gdf["nombre"] if n in config.ETIQUETAS}


@cache
def _limites_cache(clave: str) -> gpd.GeoDataFrame:
    n = obtener_nivel(clave)
    if n.tipo == "provincias":
        limites = cargar_limites("provincias")
    elif n.tipo == "departamentos":
        limites = cargar_limites("departamentos")
        limites = limites[limites["codigo"].str.startswith(n.provincia)]
    else:
        # Zonas: se disuelven las regiones del nivel base (departamentos o provincias).
        tabla = zonas(n.zonas_de)
        zona_de = dict(zip(tabla["codigo"], tabla["zona"], strict=True))
        base = _limites_cache(n.base)
        base = base.assign(codigo=base["codigo"].map(lambda c: slug(zona_de[c])))
        limites = base.dissolve(by="codigo", as_index=False)[["codigo", "geometry"]]
    limites = limites[limites["codigo"].isin(n.nombres)].copy()
    if faltan := set(n.nombres) - set(limites["codigo"]):
        raise ValueError(f"{clave}: faltan límites para {sorted(faltan)}")
    limites["nombre"] = limites["codigo"].map(n.nombres)
    return limites.reset_index(drop=True)


def _limites(nivel: str | Nivel) -> gpd.GeoDataFrame:
    """Límites actuales de las regiones del nivel (codigo, nombre, geometry)."""
    return _limites_cache(_n(nivel).clave).copy()


def regiones_censo(limites: gpd.GeoDataFrame, censo: pd.DataFrame, anio: int) -> gpd.GeoDataFrame:
    """Regiones de un censo con su peso (columna `valor`: personas o %): une las
    geometrías de las filas compuestas y omite las regiones sin dato o con 0."""
    geom = limites.set_index("codigo").geometry
    col = columna(censo, anio)
    filas = censo[censo[col].notna() & (censo[col] > 0)]
    return gpd.GeoDataFrame(
        {
            "codigo": filas["codigo"].to_list(),
            "nombre": filas["nombre"].to_list(),
            "valor": filas[col].astype(float).to_list(),
        },
        geometry=[geom.loc[partes(c)].union_all() for c in filas["codigo"]],
        crs=limites.crs,
    )


@cache
def _colores_cache(clave: str, n: int) -> dict[str, str]:
    limites = _limites(clave)
    base = AreaGrid.from_geodataframe(limites, region_col="nombre", n=n).color_map
    por_codigo = dict(zip(limites["codigo"], limites["nombre"], strict=True))
    colores = dict(base)
    for _, fila in cargar_censo(clave).iterrows():
        codigo = fila["codigo"]
        if config.SEPARADOR_COMPUESTO in codigo:
            colores[fila["nombre"]] = base[por_codigo[partes(codigo)[0]]]
    return colores


def _colores(nivel: str | Nivel, n: int) -> dict[str, str]:
    """{nombre: color}: colores de las regiones actuales, más el de cada fila
    compuesta (toma el de su primera parte)."""
    return _colores_cache(_n(nivel).clave, n)


def _lista(nombres: list[str]) -> str:
    return " y ".join(", ".join(nombres).rsplit(", ", 1))


def nota_censo(censo: pd.DataFrame, anio: int, nivel: str | Nivel) -> str:
    """Aclaraciones para un censo: datos en %, regiones unidas, regiones que no
    integraban el territorio y regiones con menos de medio bloque."""
    niv = _n(nivel)
    notas = []
    col = columna(censo, anio)
    valores = censo.set_index("codigo")[col]
    if es_porcentaje(col):
        notas.append("% publicado por el INDEC con un decimal")
        if sin_asignar := config.SIN_JURISDICCION_PCT.get(anio):
            notas.append(f"{sin_asignar:.1f}% sin provincia asignada".replace(".", ","))
    con_dato = valores.dropna()
    compuestos = [c for c in con_dato.index if config.SEPARADOR_COMPUESTO in c]
    nombres_fila = censo.set_index("codigo")["nombre"]
    notas += [f"{nombres_fila[c]}: un solo departamento" for c in compuestos]
    cubiertos = {p for c in con_dato.index for p in partes(c)}
    if faltan := sorted(set(niv.nombres) - cubiertos):
        plural = "n" if len(faltan) > 1 else ""
        nombres = _lista([niv.nombres[c] for c in faltan])
        notas.append(f"sin {nombres} (aún no integraba{plural} {niv.territorio})")
    if niv.tipo == "zonas":
        # Una zona puede estar, pero incompleta (Puna sin Los Andes en 1869).
        base = cargar_censo(niv.base)
        col_base = columna(base, anio)
        en_base = {p for c in base.loc[base[col_base].notna(), "codigo"] for p in partes(c)}
        nombres_base = obtener_nivel(niv.base).nombres
        tabla = zonas(niv.zonas_de)
        zona_de = dict(zip(tabla["codigo"], tabla["zona"], strict=True))
        for c in sorted(set(nombres_base) - en_base):
            if slug(zona_de[c]) in cubiertos:
                notas.append(
                    f"{zona_de[c]} sin {nombres_base[c]} (aún no integraba {niv.territorio})"
                )
    if ceros := [nombres_fila[c] for c in con_dato.index if con_dato[c] == 0]:
        plural = "n" if len(ceros) > 1 else ""
        notas.append(f"{_lista(ceros)}: menos de 0,05%, no llega{plural} a medio bloque")
    return "; ".join(notas)


def grilla_superficie(nivel: str | Nivel, n: int = 1000) -> AreaGrid:
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


def grilla_poblacion(
    nivel: str | Nivel, anio: int, n: int = 1000
) -> tuple[PopGrid, gpd.GeoDataFrame]:
    niv = _n(nivel)
    censo = cargar_censo(niv)
    if anio not in censos_disponibles(censo):
        raise ValueError(f"El censo {anio} no está completo para '{niv.clave}'.")
    regiones = regiones_censo(_limites(niv), censo, anio)
    colores = _colores(niv, n)
    grilla = PopGrid.from_geodataframe(
        regiones,
        region_col="nombre",
        weight_col="valor",
        n=n,
        color_map={r: colores[r] for r in regiones["nombre"] if r in colores},
    )
    return grilla, regiones


def mapa_superficie(nivel: str | Nivel, n: int = 1000) -> Figure:
    niv = _n(nivel)
    return grilla_superficie(niv, n).plot(
        title=f"Superficie de {niv.titulo}",
        subtitle=f"Cada bloque = {_pct(n)}% de la superficie {niv.unidad}",
        data_source="Límites: IGN · popgrid",
        labels=_etiquetas(_limites(niv)),
    )


def mapa_poblacion(nivel: str | Nivel, anio: int, n: int = 1000) -> Figure:
    niv = _n(nivel)
    grilla, regiones = grilla_poblacion(niv, anio, n)
    nota = nota_censo(cargar_censo(niv), anio, niv)
    return grilla.plot(
        title=f"Población de {niv.titulo} · Censo {anio}",
        subtitle=f"Cada bloque = {_pct(n)}% de la población {niv.unidad}",
        data_source=f"{nota[0].upper()}{nota[1:]} · {niv.fuente}" if nota else niv.fuente,
        labels=_etiquetas(regiones),
    )


def comparar_censos(
    nivel: str | Nivel,
    censos: list[int] | None = None,
    n: int = 1000,
    incluir_superficie: bool = True,
    columnas: int = 4,
) -> Figure:
    """Grilla de mapas: superficie (opcional) + un mapa por censo."""
    niv = _n(nivel)
    censo = cargar_censo(niv)
    censos = censos or censos_disponibles(censo)
    if not censos:
        raise ValueError("No hay ningún censo completo cargado en data/censos/.")

    paneles: list[tuple[str, AreaGrid | PopGrid, dict[str, str]]] = []
    if incluir_superficie:
        paneles.append(("Superficie", grilla_superficie(niv, n), _etiquetas(_limites(niv))))
    anios_por_nota: dict[str, list[int]] = {}
    for anio in censos:
        grilla, regiones = grilla_poblacion(niv, anio, n)
        paneles.append((f"Censo {anio}", grilla, _etiquetas(regiones)))
        for parte in filter(None, nota_censo(censo, anio, niv).split("; ")):
            anios_por_nota.setdefault(parte, []).append(anio)
    notas = [f"{_rango_censos(a, list(censos))}: {nota}" for nota, a in anios_por_nota.items()]

    # Alto de cada panel según la proporción real del territorio (Argentina es
    # alta y angosta, Salta más ancha), para no dejar franjas vacías.
    xmin, ymin, xmax, ymax = _limites(niv).to_crs(config.CRS_METRICO).total_bounds
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
        f"{niv.titulo}: superficie y población por censo",
        fontsize=18,
        fontweight="bold",
        y=1 - 0.2 / alto,
    )
    pie_texto = [f"Cada bloque = {_pct(n)}% del total · {niv.fuente}"] + notas
    fig.text(0.5, 0.12 / alto, "\n".join(pie_texto), ha="center", va="bottom", fontsize=9)
    return fig
