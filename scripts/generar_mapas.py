"""Genera los mapas de bloques en output/.

Ejemplos:
    python scripts/generar_mapas.py salta --modo comparar
    python scripts/generar_mapas.py provincias --modo poblacion --censos 2022
    python scripts/generar_mapas.py salta --modo superficie --n 2000
    python scripts/generar_mapas.py salta --modo tabla
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from popgrid_ar import config  # noqa: E402
from popgrid_ar.censos import cargar_censo, censos_disponibles, tabla_participacion  # noqa: E402
from popgrid_ar.mapas import comparar_censos, mapa_poblacion, mapa_superficie  # noqa: E402

MODOS = ("comparar", "poblacion", "superficie", "tabla", "todo")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("nivel", choices=config.NIVELES)
    parser.add_argument("--modo", choices=MODOS, default="comparar")
    parser.add_argument(
        "--censos", type=int, nargs="+", help="años (por defecto, todos los completos)"
    )
    parser.add_argument("--n", type=int, default=1000, help="cantidad de bloques (default 1000)")
    parser.add_argument("--dpi", type=int, default=170)
    parser.add_argument("--out", type=Path, default=config.SALIDA)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    censo = cargar_censo(args.nivel)
    censos = args.censos or censos_disponibles(censo)
    modos = (
        ("superficie", "poblacion", "comparar", "tabla") if args.modo == "todo" else (args.modo,)
    )

    if any(m in ("poblacion", "comparar") for m in modos) and not censos:
        parser.error(
            f"No hay censos completos en data/censos/ para '{args.nivel}'. "
            "Cargá las cifras (ver data/censos/FUENTES.md)."
        )

    def guardar(fig, nombre: str) -> None:
        ruta = args.out / nombre
        fig.savefig(ruta, dpi=args.dpi, bbox_inches="tight")
        print(f"→ {ruta}")

    for modo in modos:
        if modo == "superficie":
            guardar(mapa_superficie(args.nivel, args.n), f"{args.nivel}_superficie.png")
        elif modo == "poblacion":
            for anio in censos:
                guardar(
                    mapa_poblacion(args.nivel, anio, args.n), f"{args.nivel}_poblacion_{anio}.png"
                )
        elif modo == "comparar":
            nombre = f"{args.nivel}_comparacion_{'_'.join(map(str, censos))}.png"
            guardar(comparar_censos(args.nivel, censos, args.n), nombre)
        elif modo == "tabla":
            ruta = args.out / f"{args.nivel}_participacion.csv"
            tabla_participacion(censo).to_csv(ruta, index=False)
            print(f"→ {ruta}")


if __name__ == "__main__":
    main()
