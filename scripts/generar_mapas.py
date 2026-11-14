"""Genera los mapas de bloques en output/.

Niveles (ver popgrid_ar.niveles):
    provincias                  24 jurisdicciones, 1895-2022
    salta                       departamentos de Salta, 1869-2022 (= departamentos:66)
    departamentos:<provincia>   departamentos de cualquier provincia, 2001-2022
    zonas:salta                 zonas de Salta (data/zonas/salta.csv), 1869-2022
    zonas:argentina             regiones del país (data/zonas/argentina.csv), 1895-2022

Ejemplos:
    python scripts/generar_mapas.py salta --modo comparar
    python scripts/generar_mapas.py zonas:salta --modo todo
    python scripts/generar_mapas.py zonas:argentina --modo comparar
    python scripts/generar_mapas.py departamentos:jujuy --modo todo
    python scripts/generar_mapas.py provincias --modo poblacion --censos 2022
    python scripts/generar_mapas.py salta --modo superficie --n 2000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from popgrid_ar import config  # noqa: E402
from popgrid_ar.censos import cargar_censo, censos_disponibles, tabla_participacion  # noqa: E402
from popgrid_ar.mapas import comparar_censos, mapa_poblacion, mapa_superficie  # noqa: E402
from popgrid_ar.niveles import nivel as obtener_nivel  # noqa: E402

MODOS = ("comparar", "poblacion", "superficie", "tabla", "todo")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("nivel", help="provincias, salta, departamentos:<prov>, zonas:<prov>")
    parser.add_argument("--modo", choices=MODOS, default="comparar")
    parser.add_argument(
        "--censos", type=int, nargs="+", help="años (por defecto, todos los completos)"
    )
    parser.add_argument("--n", type=int, default=1000, help="cantidad de bloques (default 1000)")
    parser.add_argument("--dpi", type=int, default=170)
    parser.add_argument("--out", type=Path, default=config.SALIDA)
    args = parser.parse_args()

    try:
        niv = obtener_nivel(args.nivel)
    except (ValueError, FileNotFoundError) as e:
        parser.error(str(e))
    args.out.mkdir(parents=True, exist_ok=True)
    censo = cargar_censo(niv)
    censos = args.censos or censos_disponibles(censo)
    modos = (
        ("superficie", "poblacion", "comparar", "tabla") if args.modo == "todo" else (args.modo,)
    )
    prefijo = niv.archivo

    def guardar(fig, nombre: str) -> None:
        ruta = args.out / nombre
        fig.savefig(ruta, dpi=args.dpi, bbox_inches="tight")
        print(f"→ {ruta}")

    for modo in modos:
        if modo == "superficie":
            guardar(mapa_superficie(niv, args.n), f"{prefijo}_superficie.png")
        elif modo == "poblacion":
            for anio in censos:
                guardar(mapa_poblacion(niv, anio, args.n), f"{prefijo}_poblacion_{anio}.png")
        elif modo == "comparar":
            nombre = f"{prefijo}_comparacion_{censos[0]}_{censos[-1]}.png"
            guardar(comparar_censos(niv, censos, args.n), nombre)
        elif modo == "tabla":
            ruta = args.out / f"{prefijo}_participacion.csv"
            tabla_participacion(censo).to_csv(ruta, index=False)
            print(f"→ {ruta}")


if __name__ == "__main__":
    main()
