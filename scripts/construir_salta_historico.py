"""Arma data/censos/salta_historico.csv: Salta por departamento, censos 1869-2022.

Fuente: Dirección General de Estadísticas de Salta, Anuario 2025, cuadro 2.1.1
"Población según departamento. Provincia de Salta. Años 1869, 1895, 1914, 1947,
1960, 1970, 1980, 1991, 2001, 2010 y 2022" (fuente primaria: INDEC, censos nacionales).

El cuadro tiene dos particularidades que el CSV conserva tal cual:
  - Hasta 1947, Orán y General José de San Martín eran un solo departamento.
    Ese valor va en una fila compuesta con código "66126+66056"; las filas de
    Orán y de San Martín quedan vacías en esos años.
  - Los Andes (ex gobernación de Los Andes, anexada a Salta en 1943) no tiene
    dato en 1869 ni 1895. En 1914 el cuadro informa la población de los
    departamentos que luego se anexarían, y la incluye en el total.

Controles (si alguno falla, termina con error y no escribe nada):
  - en cada censo, los departamentos suman el total provincial del cuadro;
  - 2001, 2010 y 2022 coinciden con data/censos/departamentos.csv (INDEC).

Uso:
    python scripts/construir_salta_historico.py            # usa la caché
    python scripts/construir_salta_historico.py --forzar   # vuelve a descargar
"""

from __future__ import annotations

import argparse
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from popgrid_ar import config
from popgrid_ar.censos import cargar_departamentos

URL = (
    "https://estadisticas.salta.gov.ar/web/archivos/anuarios/ANUARIO-2025/"
    "02-POBLACIÓN Y HOGARES/2.01 Población/A25-2-1-1.xlsx"
)
DESTINO = config.CRUDOS / "dge_salta" / "A25-2-1-1.xlsx"
SALIDA = config.CENSOS / "salta_historico.csv"
ANIOS = (1869, 1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010, 2022)
CODIGO_ORAN_SAN_MARTIN = "66126+66056"
NOMBRE_ORAN_SAN_MARTIN = "Orán y General José de San Martín"


def _normalizar(texto) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def _numero(valor) -> int | None:
    """Convierte celdas como 60381, '60.381(4)' o '1265(2)' a entero."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return int(round(valor))
    texto = re.sub(r"\(\d+\)", "", str(valor)).replace(".", "").strip()
    return int(texto) if texto.isdigit() else None  # encabezados y notas -> None


def descargar(forzar: bool) -> Path:
    if DESTINO.exists() and not forzar:
        return DESTINO
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    ultimo_error = None
    for intento in range(4):  # el servidor a veces corta el handshake TLS
        try:
            r = requests.get(
                quote(URL, safe=":/"), timeout=60, headers={"User-Agent": "Mozilla/5.0"}
            )
            r.raise_for_status()
            if not r.content.startswith(b"PK"):
                raise ValueError("la DGE no devolvió un xlsx")
            DESTINO.write_bytes(r.content)
            print(f"  descargado {DESTINO.name}")
            return DESTINO
        except (requests.RequestException, ValueError) as e:
            ultimo_error = e
            time.sleep(2 * (intento + 1))
    raise SystemExit(f"No se pudo descargar el cuadro 2.1.1: {ultimo_error}")


def leer_cuadro(ruta: Path) -> tuple[dict[int, int], list[dict]]:
    """Devuelve (totales por año, filas {codigo, nombre, AAAA: valor})."""
    hoja = pd.read_excel(ruta, header=None)
    por_nombre = {_normalizar(n): c for c, n in config.DEPARTAMENTOS_SALTA.items()}
    por_nombre[_normalizar("General Güemes")] = "66049"  # en el cuadro: "General Güemes (1)"
    totales, filas, anterior = None, [], None
    for _, fila in hoja.iterrows():
        nombre = fila.get(1)
        valores = {a: _numero(fila.get(i + 2)) for i, a in enumerate(ANIOS)}
        if not any(v is not None for v in valores.values()):
            continue
        if isinstance(nombre, str):
            limpio = re.sub(r"\s*\(\d+\)\s*$", "", nombre).strip()
            if limpio == "Total":
                totales = valores
            elif _normalizar(limpio) in por_nombre:
                codigo = por_nombre[_normalizar(limpio)]
                filas.append(
                    {"codigo": codigo, "nombre": config.DEPARTAMENTOS_SALTA[codigo]} | valores
                )
                anterior = codigo
        elif anterior == "66126" and valores[1869] is not None:
            # Fila sin nombre debajo de Orán: Orán + San Martín hasta 1947 (nota 4).
            filas.append(
                {"codigo": CODIGO_ORAN_SAN_MARTIN, "nombre": NOMBRE_ORAN_SAN_MARTIN} | valores
            )
    if totales is None:
        raise SystemExit(f"{ruta.name}: no se encontró la fila Total")
    encontrados = {f["codigo"] for f in filas}
    faltan = set(config.DEPARTAMENTOS_SALTA) - encontrados
    if faltan or CODIGO_ORAN_SAN_MARTIN not in encontrados:
        raise SystemExit(f"{ruta.name}: faltan filas {sorted(faltan) or CODIGO_ORAN_SAN_MARTIN}")
    return totales, filas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true", help="volver a descargar de la DGE")
    args = parser.parse_args()

    totales, filas = leer_cuadro(descargar(args.forzar))
    errores = []
    for anio in ANIOS:
        suma = sum(f[anio] or 0 for f in filas)
        if suma != totales[anio]:
            errores.append(f"{anio}: departamentos suman {suma}, total {totales[anio]}")

    indec = cargar_departamentos(config.CODIGO_SALTA).set_index("codigo")
    for f in filas:
        if f["codigo"] in indec.index:
            for anio in (2001, 2010, 2022):
                if f[anio] != indec.loc[f["codigo"], f"pob_{anio}"]:
                    errores.append(f"{f['nombre']} {anio}: DGE {f[anio]} vs INDEC")

    if errores:
        raise SystemExit("No se escribió nada:\n  " + "\n  ".join(errores))

    df = pd.DataFrame(filas).rename(columns={a: f"pob_{a}" for a in ANIOS})
    df = df.sort_values("codigo")
    for a in ANIOS:
        df[f"pob_{a}"] = df[f"pob_{a}"].astype("Int64")
    df.to_csv(SALIDA, index=False)
    for a in ANIOS:
        print(f"  {a}: Salta {totales[a]:>10,}")
    print(f"Listo: {SALIDA.relative_to(config.RAIZ)} ({len(df)} filas)")


if __name__ == "__main__":
    main()
