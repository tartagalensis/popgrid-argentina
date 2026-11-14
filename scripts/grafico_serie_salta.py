"""Gráfico de líneas: % de la población de Salta por zona, censos 1869-2022.

Agrupa los 23 departamentos en cuatro zonas más "resto de la provincia", para
que la serie se lea de un vistazo. Lee data/censos/salta_historico.csv y guarda
output/salta_serie_participacion.png (+ el CSV con los valores graficados).

Uso:
    python scripts/grafico_serie_salta.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from popgrid_ar import config  # noqa: E402
from popgrid_ar.censos import cargar_censo, censos_disponibles, partes  # noqa: E402

# Zonas (códigos INDEC actuales). Orán + San Martín incluye la fila compuesta
# de 1869-1947, así que la serie es comparable en todo el período.
ZONAS = {
    "Capital": ["66028"],
    "Orán y San Martín": ["66126", "66056"],
    "Valle de Lerma (Cerrillos, R. de Lerma, Chicoana, La Caldera)": [
        "66035",
        "66147",
        "66042",
        "66077",
    ],
    "Valles Calchaquíes (Cafayate, Cachi, Molinos, San Carlos, La Poma)": [
        "66021",
        "66014",
        "66119",
        "66154",
        "66091",
    ],
}
# Paleta categórica de referencia (slots 1-4, validada) + gris neutro para el resto.
COLORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GRIS = "#9a9893"
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
ETIQUETA_CORTA = {
    "Valle de Lerma (Cerrillos, R. de Lerma, Chicoana, La Caldera)": "Valle de Lerma",
    "Valles Calchaquíes (Cafayate, Cachi, Molinos, San Carlos, La Poma)": "Valles Calchaquíes",
}


def serie() -> pd.DataFrame:
    """% de la población provincial por zona y censo (filas: censos)."""
    df = cargar_censo("salta")
    zona_de = {c: z for z, codigos in ZONAS.items() for c in codigos}
    filas = []
    for anio in censos_disponibles(df):
        col = f"pob_{anio}"
        total = df[col].sum()
        acumulado = dict.fromkeys(ZONAS, 0)
        for _, fila in df[df[col].notna()].iterrows():
            zona = zona_de.get(partes(fila["codigo"])[0])
            if zona:
                acumulado[zona] += fila[col]
        fila_pct = {z: v / total * 100 for z, v in acumulado.items()}
        fila_pct["Resto de la provincia"] = 100 - sum(fila_pct.values())
        filas.append({"censo": anio} | fila_pct)
    return pd.DataFrame(filas).set_index("censo")


def main() -> None:
    datos = serie()
    config.SALIDA.mkdir(parents=True, exist_ok=True)
    datos.round(1).to_csv(config.SALIDA / "salta_serie_participacion.csv")

    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    series = [*ZONAS, "Resto de la provincia"]
    colores = [*COLORES, GRIS]
    anios = datos.index.to_list()
    for nombre, color in zip(series, colores, strict=True):
        y = datos[nombre]
        es_resto = nombre == "Resto de la provincia"
        ax.plot(
            anios,
            y,
            color=color,
            linewidth=2,
            linestyle=(0, (4, 3)) if es_resto else "-",
            marker="o",
            markersize=6,
            markeredgecolor=SUPERFICIE,
            markeredgewidth=1.5,
            zorder=2 if es_resto else 3,
        )
        # Etiqueta directa al final de la línea (nombre + valor 2022), en tinta, no en color.
        corto = ETIQUETA_CORTA.get(nombre, nombre)
        ax.annotate(
            f"{corto}  {y.iloc[-1]:.1f}%".replace(".", ","),
            xy=(anios[-1], y.iloc[-1]),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            fontsize=10.5,
            color=TINTA if not es_resto else TINTA_2,
            fontweight="bold" if not es_resto else "normal",
        )

    ax.set_xticks(anios)
    ax.set_xticklabels(anios, fontsize=9.5, color=TINTA_2)
    ax.set_xlim(anios[0] - 4, anios[-1] + 4)
    ax.set_ylim(0, 50)
    ax.set_yticks(range(0, 51, 10))
    ax.set_yticklabels([f"{v}%" for v in range(0, 51, 10)], fontsize=9.5, color=TINTA_2)
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.tick_params(length=0)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c3")

    fig.text(
        0.06,
        0.95,
        "Salta: dónde vive la gente, 1869-2022",
        fontsize=17,
        fontweight="bold",
        color=TINTA,
    )
    fig.text(
        0.06,
        0.905,
        "% de la población provincial en cada censo nacional",
        fontsize=11.5,
        color=TINTA_2,
    )
    fig.text(
        0.06,
        0.025,
        "Fuente: INDEC, censos nacionales (serie de la Dirección General de Estadísticas de "
        "Salta, Anuario 2025, cuadro 2.1.1).\n"
        "Orán y San Martín fueron un solo departamento hasta 1947. Los Andes, anexado a "
        "Salta en 1943, cuenta en «Resto» desde 1914.\n"
        "Los censos no son equidistantes: el eje horizontal respeta la distancia entre años.",
        fontsize=8.5,
        color=TINTA_2,
        linespacing=1.5,
    )
    fig.subplots_adjust(left=0.06, right=0.8, top=0.86, bottom=0.17)
    ruta = config.SALIDA / "salta_serie_participacion.png"
    fig.savefig(ruta, dpi=170, facecolor=SUPERFICIE)
    print(f"→ {ruta}")
    print(datos.round(1).to_string())


if __name__ == "__main__":
    main()
