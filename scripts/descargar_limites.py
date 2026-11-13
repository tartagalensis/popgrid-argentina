"""Descarga los departamentos del IGN y genera los límites simplificados.

Uso:
    python scripts/descargar_limites.py            # descarga (si falta) y construye
    python scripts/descargar_limites.py --forzar   # vuelve a descargar
"""

from __future__ import annotations

import argparse

from popgrid_ar.limites import construir_limites, descargar_departamentos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true", help="volver a descargar del IGN")
    args = parser.parse_args()

    crudo = descargar_departamentos(forzar=args.forzar)
    construir_limites(crudo)


if __name__ == "__main__":
    main()
