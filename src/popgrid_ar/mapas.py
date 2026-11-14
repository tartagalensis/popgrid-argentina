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
import re
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
from .variables import Variable
from .variables import variable as obtener_variable


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


def _fuente(niv: Nivel, var: Variable) -> str:
    if var.clave == "poblacion":
        return niv.fuente
    return f"Límites: IGN · {var.fuente} · popgrid"


def nota_censo(
    censo: pd.DataFrame, anio: int, nivel: str | Nivel, variable: str | Variable = "poblacion"
) -> str:
    """Aclaraciones para un año: datos en %, valores sin provincia, datos
    provisorios, regiones unidas, regiones que no integraban el territorio y
    regiones con menos de medio bloque."""
    niv = _n(nivel)
    var = obtener_variable(variable)
    notas = []
    col = columna(censo, anio)
    valores = censo.set_index("codigo")[col]
    if es_porcentaje(col):
        notas.append("% publicado por el INDEC con un decimal")
    base_provincias = niv.tipo == "provincias" or (niv.tipo == "zonas" and niv.base == "provincias")
    if base_provincias and (sin_asignar := var.sin_provincia_pct(anio)) and sin_asignar >= 0.05:
        notas.append(f"{sin_asignar:.1f}% {var.de} sin provincia asignada".replace(".", ","))
    if anio in var.provisorios:
        notas.append("datos provisorios")
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
        base = cargar_censo(niv.base, var)
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
    """'1869 a 1947' si son años consecutivos de la serie; si no, '1869, 1914'."""
    i = todos.index(anios[0])
    if len(anios) > 2 and todos[i : i + len(anios)] == anios:
        return f"{anios[0]} a {anios[-1]}"
    return " y ".join(", ".join(map(str, anios)).rsplit(", ", 1))


def grilla_variable(
    nivel: str | Nivel, anio: int, n: int = 1000, variable: str | Variable = "poblacion"
) -> tuple[PopGrid, gpd.GeoDataFrame]:
    """Grilla de bloques de una variable en un año (o censo)."""
    niv = _n(nivel)
    var = obtener_variable(variable)
    datos = cargar_censo(niv, var)
    if anio not in censos_disponibles(datos):
        raise ValueError(f"{var.titulo} {anio} no está completo para '{niv.clave}'.")
    regiones = regiones_censo(_limites(niv), datos, anio)
    colores = _colores(niv, n)
    grilla = PopGrid.from_geodataframe(
        regiones,
        region_col="nombre",
        weight_col="valor",
        n=n,
        color_map={r: colores[r] for r in regiones["nombre"] if r in colores},
    )
    return grilla, regiones


def grilla_poblacion(
    nivel: str | Nivel, anio: int, n: int = 1000
) -> tuple[PopGrid, gpd.GeoDataFrame]:
    return grilla_variable(nivel, anio, n, "poblacion")


def mapa_superficie(nivel: str | Nivel, n: int = 1000) -> Figure:
    niv = _n(nivel)
    return grilla_superficie(niv, n).plot(
        title=f"Superficie de {niv.titulo}",
        subtitle=f"Cada bloque = {_pct(n)}% de la superficie {niv.unidad}",
        data_source="Límites: IGN · popgrid",
        labels=_etiquetas(_limites(niv)),
    )


def mapa_variable(
    nivel: str | Nivel, anio: int, n: int = 1000, variable: str | Variable = "poblacion"
) -> Figure:
    niv = _n(nivel)
    var = obtener_variable(variable)
    grilla, regiones = grilla_variable(niv, anio, n, var)
    nota = nota_censo(cargar_censo(niv, var), anio, niv, var)
    fuente = _fuente(niv, var)
    return grilla.plot(
        title=f"{var.titulo} de {niv.titulo} · {var.etiqueta(anio)}",
        subtitle=f"Cada bloque = {_pct(n)}% {var.de} {niv.unidad}",
        data_source=f"{nota[0].upper()}{nota[1:]} · {fuente}" if nota else fuente,
        labels=_etiquetas(regiones),
    )


def mapa_poblacion(nivel: str | Nivel, anio: int, n: int = 1000) -> Figure:
    return mapa_variable(nivel, anio, n, "poblacion")


def _agrupar_notas(anios_por_nota: dict[str, list[int]], todos: list[int]) -> list[str]:
    """Une notas que solo cambian en el porcentaje ('4,3% de las exportaciones sin
    provincia asignada' en cada año) en una sola línea:
    '% de las exportaciones sin provincia asignada: 1993 4,3%, 1995 3,9%, ...'.
    Con más de 4 años, informa el rango: 'entre 1,5% y 6,2% según el año'."""
    salida, por_sufijo = [], {}
    for nota, anios in anios_por_nota.items():
        m = re.fullmatch(r"([\d,]+)% (.+)", nota)
        if m:
            valor = float(m.group(1).replace(",", "."))
            por_sufijo.setdefault(m.group(2), []).extend((a, valor) for a in anios)
        else:
            salida.append(f"{_rango_censos(anios, todos)}: {nota}")
    for sufijo, pares in por_sufijo.items():
        pares.sort()
        if len(pares) > 4:
            bajo, alto = min(v for _, v in pares), max(v for _, v in pares)
            texto = (
                f"entre {bajo:.1f}% y {alto:.1f}% según el año ({pares[0][0]}-{pares[-1][0]})"
            ).replace(".", ",")
        else:
            texto = ", ".join(f"{a} {v:.1f}%".replace(".", ",") for a, v in pares)
        salida.insert(0, f"% {sufijo}: {texto}")
    return salida


def _figura_paneles(
    niv: Nivel,
    paneles: list[tuple[str, AreaGrid | PopGrid, dict[str, str]]],
    titulo: str,
    pie: list[str],
    columnas: int,
) -> Figure:
    """Grilla de paneles de bloques con título y pie."""
    # Alto de cada panel según la proporción real del territorio (Argentina es
    # alta y angosta, Salta más ancha), para no dejar franjas vacías.
    xmin, ymin, xmax, ymax = _limites(niv).to_crs(config.CRS_METRICO).total_bounds
    ncols = min(columnas, len(paneles))
    nfilas = math.ceil(len(paneles) / ncols)
    ancho_panel = 4.5
    alto_panel = ancho_panel * min(max((ymax - ymin) / (xmax - xmin), 0.6), 2.2)
    alto_pie = 0.25 + 0.22 * len(pie)
    alto = alto_panel * nfilas + 0.95 + alto_pie
    fig, ejes = plt.subplots(nfilas, ncols, figsize=(ancho_panel * ncols, alto), squeeze=False)
    fig.subplots_adjust(
        left=0.01,
        right=0.99,
        top=1 - 0.95 / alto,
        bottom=alto_pie / alto,
        wspace=0.04,
        hspace=0.12,
    )
    ejes = list(ejes.flat)
    for ax, (titulo_panel, grilla, etiquetas) in zip(ejes, paneles, strict=False):
        grilla.draw(ax, background_style="none", labels=etiquetas)
        ax.set_title(titulo_panel, fontsize=14, fontweight="bold")
    for ax in ejes[len(paneles) :]:
        ax.set_axis_off()
    fig.suptitle(titulo, fontsize=18, fontweight="bold", y=1 - 0.2 / alto)
    fig.text(0.5, 0.12 / alto, "\n".join(pie), ha="center", va="bottom", fontsize=9)
    return fig


def comparar_censos(
    nivel: str | Nivel,
    censos: list[int] | None = None,
    n: int = 1000,
    incluir_superficie: bool = True,
    columnas: int = 4,
    variable: str | Variable = "poblacion",
) -> Figure:
    """Grilla de mapas: superficie (opcional) + un mapa por año (o censo)."""
    niv = _n(nivel)
    var = obtener_variable(variable)
    datos = cargar_censo(niv, var)
    anios = censos or var.anios_por_defecto(censos_disponibles(datos))
    if not anios:
        raise ValueError("No hay ningún año completo cargado.")

    paneles: list[tuple[str, AreaGrid | PopGrid, dict[str, str]]] = []
    if incluir_superficie:
        paneles.append(("Superficie", grilla_superficie(niv, n), _etiquetas(_limites(niv))))
    anios_por_nota: dict[str, list[int]] = {}
    for anio in anios:
        grilla, regiones = grilla_variable(niv, anio, n, var)
        paneles.append((var.etiqueta(anio), grilla, _etiquetas(regiones)))
        for parte in filter(None, nota_censo(datos, anio, niv, var).split("; ")):
            anios_por_nota.setdefault(parte, []).append(anio)
    notas = _agrupar_notas(anios_por_nota, list(anios))
    periodo = "censo" if var.periodo == "censo" else "año"
    return _figura_paneles(
        niv,
        paneles,
        f"{niv.titulo}: superficie y {var.nombre} por {periodo}",
        [f"Cada bloque = {_pct(n)}% del total · {_fuente(niv, var)}", *notas],
        columnas,
    )


def comparar_variables(
    nivel: str | Nivel,
    anio: int,
    variables: tuple[str, ...] = ("poblacion", "exportaciones"),
    n: int = 1000,
) -> Figure:
    """Superficie + una variable por panel, para un mismo año. Si una variable no
    tiene ese año (p. ej. población fuera de un censo),
    usa el año disponible más cercano y lo indica en el título del panel."""
    niv = _n(nivel)
    paneles: list[tuple[str, AreaGrid | PopGrid, dict[str, str]]] = [
        ("Superficie", grilla_superficie(niv, n), _etiquetas(_limites(niv)))
    ]
    pie = [f"Cada bloque = {_pct(n)}% del total de cada variable · Límites: IGN · popgrid"]
    for clave in variables:
        var = obtener_variable(clave)
        datos = cargar_censo(niv, var)
        disponibles = censos_disponibles(datos)
        usado = min(disponibles, key=lambda a: (abs(a - anio), -a))
        grilla, regiones = grilla_variable(niv, usado, n, var)
        paneles.append((f"{var.titulo} · {var.etiqueta(usado)}", grilla, _etiquetas(regiones)))
        nota = nota_censo(datos, usado, niv, var)
        pie.append(f"{var.fuente}" + (f" ({nota})" if nota else ""))
    nombres = _lista([obtener_variable(v).nombre for v in variables])
    return _figura_paneles(
        niv, paneles, f"{niv.titulo}: superficie, {nombres}", pie, columnas=len(paneles)
    )
