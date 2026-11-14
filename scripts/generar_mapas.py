"""Genera los mapas de bloques en output/.

Niveles (ver popgrid_ar.niveles):
    provincias                  24 jurisdicciones, 1895-2022
    salta                       departamentos de Salta, 1869-2022 (= departamentos:66)
    departamentos:<provincia>   departamentos de cualquier provincia, 2001-2022
    zonas:salta                 zonas de Salta (data/zonas/salta.csv), 1869-2022
    zonas:argentina             regiones del país (data/zonas/argentina.csv), 1895-2022

Variables (--variable): poblacion (por defecto), exportaciones, pbi.

Ejemplos:
    python scripts/generar_mapas.py salta --modo comparar
    python scripts/generar_mapas.py provincias --variable exportaciones --modo comparar
    python scripts/generar_mapas.py zonas:argentina --modo variables --anio 2022
    python scripts/generar_mapas.py zonas:salta --variable pbi --modo todo
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
from popgrid_ar.mapas import (  # noqa: E402
    comparar_censos,
    comparar_variables,
    mapa_superficie,
    mapa_variable,
)
from popgrid_ar.niveles import nivel as obtener_nivel  # noqa: E402
from popgrid_ar.variables import VARIABLES  # noqa: E402
from popgrid_ar.variables import variable as obtener_variable  # noqa: E402

MODOS = ("comparar", "poblacion", "superficie", "tabla", "variables", "todo")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("nivel", help="provincias, salta, departamentos:<prov>, zonas:<prov>")
    parser.add_argument("--modo", choices=MODOS, default="comparar")
    parser.add_argument("--variable", choices=sorted(VARIABLES), default="poblacion")
    parser.add_argument(
        "--anio", type=int, default=2022, help="año para --modo variables (default 2022)"
    )
    parser.add_argument(
        "--censos",
        "--anios",
        dest="censos",
        type=int,
        nargs="+",
        help="censos o años (por defecto: todos los censos, o una selección de años)",
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
    var = obtener_variable(args.variable)
    censo = cargar_censo(niv, var)
    disponibles = censos_disponibles(censo)
    censos = args.censos or var.anios_por_defecto(disponibles)
    modos = (
        ("superficie", "poblacion", "comparar", "tabla") if args.modo == "todo" else (args.modo,)
    )
    prefijo = niv.archivo if var.clave == "poblacion" else f"{niv.archivo}_{var.clave}"

    def guardar(fig, nombre: str) -> None:
        ruta = args.out / nombre
        fig.savefig(ruta, dpi=args.dpi, bbox_inches="tight")
        print(f"→ {ruta}")

    for modo in modos:
        if modo == "superficie":
            guardar(mapa_superficie(niv, args.n), f"{niv.archivo}_superficie.png")
        elif modo == "poblacion":
            for anio in censos:
                guardar(
                    mapa_variable(niv, anio, args.n, var), f"{niv.archivo}_{var.clave}_{anio}.png"
                )
        elif modo == "comparar":
            nombre = f"{prefijo}_comparacion_{censos[0]}_{censos[-1]}.png"
            guardar(comparar_censos(niv, censos, args.n, variable=var), nombre)
        elif modo == "variables":
            nombre = f"{niv.archivo}_variables_{args.anio}.png"
            guardar(comparar_variables(niv, args.anio, n=args.n), nombre)
        elif modo == "tabla":
            ruta = args.out / f"{prefijo}_participacion.csv"
            tabla_participacion(censo).to_csv(ruta, index=False)
            print(f"→ {ruta}")


if __name__ == "__main__":
    main()
