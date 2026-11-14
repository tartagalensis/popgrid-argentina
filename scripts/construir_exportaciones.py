"""Arma data/economia/exportaciones_*.csv: exportaciones por provincia de origen, 1993-2025.

Fuente: INDEC, Origen provincial de las exportaciones (OPEX), serie
"sh_opex_regiones_economicas_provincias_1993_2025.xls" (millones de USD).

Salidas:
    data/economia/exportaciones_provincias.csv  codigo,nombre,val_1993,...  (24 provincias)
    data/economia/exportaciones_otros.csv       concepto,val_1993,...       (Total, Extranjero y
                                                plataforma continental, Indeterminado)

Los años marcados con * en el cuadro son provisorios; se listan en FUENTES.md.

Control (si falla, termina con error y no escribe nada): en cada año, las 24
provincias más "Extranjero y plataforma continental" más "Indeterminado" suman el
Total del cuadro (tolerancia por redondeo: 0,1% o 1 millón de USD).

Uso:
    python scripts/construir_exportaciones.py            # usa la caché
    python scripts/construir_exportaciones.py --forzar   # vuelve a descargar
"""

from __future__ import annotations

import argparse
import re
import unicodedata

import pandas as pd
import requests

from popgrid_ar import config

ARCHIVO = "sh_opex_regiones_economicas_provincias_1993_2025.xls"
URL = f"https://www.indec.gob.ar/ftp/cuadros/economia/{ARCHIVO}"
DESTINO = config.CRUDOS / "indec" / ARCHIVO
OTROS = ("Extranjero y plataforma continental", "Indeterminado")
ALIAS = {
    "ciudad autonoma de buenos aires": "02",
    "tierra del fuego, antartida e islas del atlantico sur": "94",
}


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def descargar(forzar: bool):
    if DESTINO.exists() and not forzar:
        return DESTINO
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if not r.content.startswith(b"\xd0\xcf\x11\xe0"):
        raise SystemExit("El INDEC no devolvió un .xls")
    DESTINO.write_bytes(r.content)
    print(f"  descargado {ARCHIVO}")
    return DESTINO


def _anio(celda) -> tuple[int, bool] | None:
    """2025 / '2025*' -> (2025, provisorio)."""
    m = re.fullmatch(r"(\d{4})(?:\.0)?(\*?)", str(celda).strip())
    return (int(m.group(1)), bool(m.group(2))) if m else None


def leer_hoja(df: pd.DataFrame) -> tuple[dict[str, dict[int, float]], set[int]]:
    """Devuelve ({nombre de fila: {año: valor}}, años provisorios)."""
    fila_unidad = next(i for i in range(len(df)) if str(df.iat[i, 2]).strip() == "Millones de USD")
    anios = {}
    for j in range(2, df.shape[1]):
        a = _anio(df.iat[fila_unidad - 1, j])
        if a is None:
            break
        anios[j] = a
    filas = {}
    for i in range(fila_unidad + 1, len(df)):
        region, provincia = df.iat[i, 0], df.iat[i, 1]
        nombre = provincia if isinstance(provincia, str) else region
        if not isinstance(nombre, str):
            continue
        nombre = re.sub(r"\s+", " ", nombre).strip()
        if nombre in ("Total", *OTROS) or isinstance(provincia, str):
            valores = {a: float(df.iat[i, j]) for j, (a, _) in anios.items()}
            filas[nombre] = valores
    return filas, {a for a, prov in anios.values() if prov}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true", help="volver a descargar")
    args = parser.parse_args()

    libro = pd.read_excel(descargar(args.forzar), sheet_name=None, header=None)
    nombres = {_normalizar(n): c for c, n in config.PROVINCIAS.items()} | ALIAS
    provincias: dict[str, dict[int, float]] = {c: {} for c in config.PROVINCIAS}
    otros: dict[str, dict[int, float]] = {o: {} for o in ("Total", *OTROS)}
    provisorios: set[int] = set()
    for hoja, df in libro.items():
        filas, prov = leer_hoja(df)
        provisorios |= prov
        for nombre, valores in filas.items():
            if nombre in otros:
                otros[nombre].update(valores)
            elif _normalizar(nombre) in nombres:
                provincias[nombres[_normalizar(nombre)]].update(valores)
            else:
                raise SystemExit(f"Hoja {hoja}: fila desconocida {nombre!r}")

    anios = sorted(otros["Total"])
    errores = []
    for c, valores in provincias.items():
        if faltan := set(anios) - set(valores):
            errores.append(f"{config.PROVINCIAS[c]}: faltan años {sorted(faltan)}")
    for a in anios:
        suma = sum(v[a] for v in provincias.values()) + sum(otros[o][a] for o in OTROS)
        total = otros["Total"][a]
        if abs(suma - total) > max(1.0, total * 0.001):
            errores.append(f"{a}: provincias + otros = {suma:.0f}, Total = {total:.0f}")
    if errores:
        raise SystemExit("No se escribió nada:\n  " + "\n  ".join(errores))

    destino = config.ECONOMIA
    destino.mkdir(parents=True, exist_ok=True)
    prov_df = pd.DataFrame(
        [
            {"codigo": c, "nombre": config.PROVINCIAS[c]}
            | {f"val_{a}": round(v[a], 3) for a in anios}
            for c, v in sorted(provincias.items())
        ]
    )
    prov_df.to_csv(destino / "exportaciones_provincias.csv", index=False)
    otros_df = pd.DataFrame(
        [{"concepto": o} | {f"val_{a}": round(v[a], 3) for a in anios} for o, v in otros.items()]
    )
    otros_df.to_csv(destino / "exportaciones_otros.csv", index=False)
    print(f"  {anios[0]}-{anios[-1]} ({len(anios)} años); provisorios: {sorted(provisorios)}")
    for a in (anios[0], 2001, 2010, 2022, anios[-1]):
        sin = sum(otros[o][a] for o in OTROS) / otros["Total"][a] * 100
        print(f"  {a}: total {otros['Total'][a]:>9,.0f} M USD · sin provincia {sin:.1f}%")
    print("Listo: data/economia/exportaciones_provincias.csv y exportaciones_otros.csv")


if __name__ == "__main__":
    main()
