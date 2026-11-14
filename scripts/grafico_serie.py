"""Serie de participación (% del total) por región, en paneles chicos.

Un panel por región, con el mismo color que la región tiene en el mapa de
bloques. Cada panel tiene su propia escala vertical (empieza siempre en 0), para
que se vea la dinámica de las regiones chicas; el valor del primer y del último
censo va escrito en el panel.

Uso:
    python scripts/grafico_serie.py zonas:salta
    python scripts/grafico_serie.py zonas:argentina
    python scripts/grafico_serie.py provincias --columnas 6
    python scripts/grafico_serie.py zonas:argentina --variable exportaciones

Guarda output/<nivel>_serie.png y output/<nivel>_serie.csv (los valores graficados).
"""

from __future__ import annotations

import argparse
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from popgrid_ar import config  # noqa: E402
from popgrid_ar.censos import (  # noqa: E402
    cargar_censo,
    censos_disponibles,
    columna,
    es_porcentaje,
)
from popgrid_ar.mapas import _agrupar_notas, _colores, nota_censo  # noqa: E402
from popgrid_ar.niveles import nivel as obtener_nivel  # noqa: E402
from popgrid_ar.variables import VARIABLES  # noqa: E402
from popgrid_ar.variables import variable as obtener_variable  # noqa: E402

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRILLA = "#ecebe8"


def _num(v: float, decimales: int = 1) -> str:
    return f"{v:.{decimales}f}".replace(".", ",")


def serie(clave: str, variable: str = "poblacion") -> pd.DataFrame:
    """% del total por región (columnas) y censo (filas). Las filas compuestas
    (Orán + San Martín) se asignan a su primera parte."""
    censo = cargar_censo(clave, variable)
    niv = obtener_nivel(clave)
    # Sin redondeos intermedios: % calculado desde las personas (o el % publicado).
    tabla = censo[["codigo"]].copy()
    for anio in censos_disponibles(censo):
        col = columna(censo, anio)
        valores = censo[col].astype(float)
        tabla[anio] = valores if es_porcentaje(col) else valores / valores.sum() * 100
    tabla["region"] = tabla["codigo"].map(
        lambda c: niv.nombres[c.split(config.SEPARADOR_COMPUESTO)[0]]
    )
    datos = tabla.drop(columns="codigo").groupby("region", sort=False).sum(min_count=1).T
    return datos[list(niv.nombres.values())]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("nivel")
    parser.add_argument("--columnas", type=int, default=4)
    parser.add_argument("--variable", choices=sorted(VARIABLES), default="poblacion")
    args = parser.parse_args()

    niv = obtener_nivel(args.nivel)
    var = obtener_variable(args.variable)
    datos = serie(niv.clave, var.clave)
    prefijo = niv.archivo if var.clave == "poblacion" else f"{niv.archivo}_{var.clave}"
    colores = _colores(niv, 1000)
    config.SALIDA.mkdir(parents=True, exist_ok=True)
    datos.round(2).to_csv(config.SALIDA / f"{prefijo}_serie.csv", index_label="censo")

    regiones = list(datos.columns)
    ncols = min(args.columnas, len(regiones))
    nfilas = math.ceil(len(regiones) / ncols)
    fig, ejes = plt.subplots(
        nfilas,
        ncols,
        figsize=(3.6 * ncols, 2.5 * nfilas + 1.6),
        squeeze=False,
        facecolor=SUPERFICIE,
    )
    anios = datos.index.to_list()
    for ax, region in zip(ejes.flat, regiones, strict=False):
        ax.set_facecolor(SUPERFICIE)
        y = datos[region]
        ax.plot(anios, y, color=colores[region], linewidth=2.2, zorder=3)
        validos = y.dropna()
        # Series largas (anuales): solo se marcan los extremos.
        marcas = validos if len(validos) <= 15 else validos.iloc[[0, -1]]
        ax.scatter(
            marcas.index,
            marcas,
            s=14,
            color=colores[region],
            zorder=4,
            edgecolors=SUPERFICIE,
            linewidths=0.8,
        )
        tope = max(validos.max() * 1.35, 1)
        ax.set_ylim(0, tope)
        ax.set_xlim(anios[0] - 5, anios[-1] + 5)
        ax.set_title(region, fontsize=11.5, fontweight="bold", color=TINTA, loc="left")
        primero, ultimo = validos.index[0], validos.index[-1]
        ax.annotate(
            f"{_num(validos.iloc[0])}%",
            (primero, validos.iloc[0]),
            xytext=(0, 7),
            textcoords="offset points",
            ha="left",
            fontsize=9,
            color=TINTA_2,
        )
        ax.annotate(
            f"{_num(validos.iloc[-1])}%",
            (ultimo, validos.iloc[-1]),
            xytext=(0, 7),
            textcoords="offset points",
            ha="right",
            fontsize=9.5,
            color=TINTA,
            fontweight="bold",
        )
        ax.yaxis.set_major_locator(MaxNLocator(nbins=2, steps=[1, 2, 5, 10]))
        decimales = 0 if tope >= 5 else 1
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _, d=decimales: f"{_num(v, d)}%"))
        ax.tick_params(axis="y", labelsize=8, colors=TINTA_2)
        ax.set_xticks([anios[0], 1947 if 1947 in anios else anios[len(anios) // 2], anios[-1]])
        ax.tick_params(axis="x", labelsize=8, colors=TINTA_2, length=0)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", color=GRILLA, linewidth=0.8)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color("#c9c8c3")
    for ax in list(ejes.flat)[len(regiones) :]:
        ax.set_axis_off()

    fig.text(
        0.02,
        1 - 0.35 / fig.get_figheight(),
        f"{niv.titulo}: % {var.de} en cada {'censo' if var.periodo == 'censo' else 'año'}",
        fontsize=15,
        fontweight="bold",
        color=TINTA,
        va="top",
    )
    fig.text(
        0.02,
        1 - 0.75 / fig.get_figheight(),
        "La escala vertical cambia de panel a panel: mirá la forma de cada línea "
        "y los valores escritos.",
        fontsize=9.5,
        color=TINTA_2,
        va="top",
    )
    censo = cargar_censo(niv, var)
    anios_por_nota: dict[str, list[int]] = {}
    for anio in anios:
        for parte in filter(None, nota_censo(censo, anio, niv, var).split("; ")):
            anios_por_nota.setdefault(parte, []).append(anio)
    fuente = (
        niv.fuente.replace("Límites: IGN · Población: ", "").replace(" · popgrid", "")
        if var.clave == "poblacion"
        else var.fuente.split(": ", 1)[1]
    )
    pie = f"Fuente: {fuente}."
    if anios_por_nota:
        pie += " Notas: " + "; ".join(_agrupar_notas(anios_por_nota, anios)) + "."
    fig.text(0.02, 0.012, pie, fontsize=7.5, color=TINTA_2, wrap=True)
    fig.subplots_adjust(
        left=0.05,
        right=0.98,
        top=1 - 1.25 / fig.get_figheight(),
        bottom=0.55 / fig.get_figheight() + 0.03,
        hspace=0.75,
        wspace=0.28,
    )
    ruta = config.SALIDA / f"{prefijo}_serie.png"
    fig.savefig(ruta, dpi=170, facecolor=SUPERFICIE)
    print(f"→ {ruta}")
    print(datos.round(1).to_string())


if __name__ == "__main__":
    main()
