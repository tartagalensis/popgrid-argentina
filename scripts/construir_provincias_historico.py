"""Arma data/censos/provincias_historico.csv: % de población por provincia, 1895-1991.

Fuente: INDEC, Censo 2010, Resultados definitivos, Serie B nº 2, Tomo 1, Cuadro 7
"Distribución relativa de la población según provincia. Total del país.
Años 1895/2010" (página 63 de la publicación, 64 del PDF).

El INDEC publica esta serie solo en porcentajes con un decimal (no en cantidades
de personas). Con 1.000 bloques, cada bloque es el 0,1%, así que alcanza para
los mapas. Se guardan los censos 1895 a 1991; 2001 y 2010 se usan como control
contra provincias.csv (que tiene cantidades exactas).

Signos del cuadro:
  - "–" en Tierra del Fuego (1895-1947): menos de 0,05%. Se guarda como 0.
  - "0,0" (Santa Cruz 1895): idem.
Esas provincias no llegan a medio bloque y no se dibujan en esos censos.

Controles (si alguno falla, termina con error y no escribe nada):
  - 24 provincias, 9 valores por fila;
  - cada censo suma 100 ± 0,6 sumando "jurisdicciones sin determinar";
  - 2001 y 2010 coinciden (redondeados a un decimal) con provincias.csv.

Uso:
    python scripts/construir_provincias_historico.py            # usa la caché
    python scripts/construir_provincias_historico.py --forzar   # vuelve a descargar
"""

from __future__ import annotations

import argparse
import re
import unicodedata

import pandas as pd
import pypdf
import requests

from popgrid_ar import config
from popgrid_ar.censos import cargar_censo

URL = "https://www.indec.gob.ar/ftp/cuadros/poblacion/censo2010_tomo1.pdf"
DESTINO = config.CRUDOS / "indec" / "censo2010_tomo1.pdf"
PAGINA = 63  # índice 0: página 64 del PDF, 63 de la publicación
SALIDA = config.CENSOS / "provincias_historico.csv"
ANIOS = (1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010)
GUARDAR = (1895, 1914, 1947, 1960, 1970, 1980, 1991)
ALIAS = {
    "ciudad autonoma de buenos aires": "02",
    "tierra del fuego, antartida e islas del atlantico sur": "94",
}
_VALOR = r"(?:\d+,\d|\d+|–+)"


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def descargar(forzar: bool):
    if DESTINO.exists() and not forzar:
        return DESTINO
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=300, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise SystemExit("El INDEC no devolvió un PDF")
    DESTINO.write_bytes(r.content)
    print(f"  descargado {DESTINO.name}")
    return DESTINO


def _valor(token: str) -> float:
    return 0.0 if token.startswith("–") else float(token.replace(",", "."))


def leer_cuadro(ruta) -> tuple[dict[str, list[float]], list[float]]:
    texto = pypdf.PdfReader(ruta).pages[PAGINA].extract_text(extraction_mode="layout")
    if "Cuadro 7. Distribución relativa de la población según provincia" not in texto:
        raise SystemExit("La página no es el Cuadro 7: revisar PAGINA")
    nombres = {_normalizar(n): c for c, n in config.PROVINCIAS.items()}
    nombres.pop(_normalizar("CABA"))
    nombres.pop(_normalizar("Tierra del Fuego"))
    nombres |= ALIAS
    filas, sin_determinar = {}, None
    patron = re.compile(rf"^\s*(.+?)\s*(?:\(\d\))?\s+((?:{_VALOR}\s+){{8}}{_VALOR})\s*$")
    for linea in texto.splitlines():
        if "sin determinar" in linea:
            valores = re.findall(r"\d+,\d", linea)
            sin_determinar = [_valor(v) for v in valores] + [0.0] * (9 - len(valores))
            continue
        m = patron.match(linea)
        if not m:
            continue
        nombre = _normalizar(m.group(1))
        valores = [_valor(t) for t in m.group(2).split()]
        if nombre in nombres:
            filas[nombres[nombre]] = valores
    faltan = set(config.PROVINCIAS) - set(filas)
    if faltan or sin_determinar is None:
        raise SystemExit(
            f"No se pudieron leer: {sorted(faltan) or 'jurisdicciones sin determinar'}"
        )
    return filas, sin_determinar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true", help="volver a descargar el PDF")
    args = parser.parse_args()

    filas, sin_determinar = leer_cuadro(descargar(args.forzar))
    errores = []
    for i, anio in enumerate(ANIOS):
        suma = sum(v[i] for v in filas.values()) + sin_determinar[i]
        if abs(suma - 100) > 0.6:
            errores.append(f"{anio}: la columna suma {suma:.1f}")

    # Tolerancia de una décima: el INDEC redondea algunos casos hacia arriba
    # (p. ej. Buenos Aires 2010: 38,949% exacto, 39,0 publicado).
    exactos = cargar_censo("provincias").set_index("codigo")
    max_dif = 0.0
    for anio in (2001, 2010):
        pct = (exactos[f"pob_{anio}"] / exactos[f"pob_{anio}"].sum() * 100).astype(float)
        for codigo, valores in filas.items():
            publicado = valores[ANIOS.index(anio)]
            max_dif = max(max_dif, abs(publicado - pct[codigo]))
            if abs(publicado - pct[codigo]) > 0.1:
                errores.append(
                    f"{config.PROVINCIAS[codigo]} {anio}: cuadro {publicado} vs {pct[codigo]:.2f}"
                )

    if errores:
        raise SystemExit("No se escribió nada:\n  " + "\n  ".join(errores))

    df = pd.DataFrame(
        [
            {"codigo": c, "nombre": config.PROVINCIAS[c]}
            | {f"pct_{a}": v[ANIOS.index(a)] for a in GUARDAR}
            for c, v in sorted(filas.items())
        ]
    )
    df.to_csv(SALIDA, index=False)
    print(f"  control 2001/2010: diferencia máxima {max_dif:.3f} puntos porcentuales")
    print("  sin determinar:", dict(zip(ANIOS, sin_determinar, strict=True)))
    print(f"Listo: {SALIDA.relative_to(config.RAIZ)} ({len(df)} provincias)")


if __name__ == "__main__":
    main()
