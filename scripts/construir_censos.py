"""Descarga los cuadros oficiales del INDEC y arma data/censos/*.csv.

Salidas:
    data/censos/provincias.csv     24 jurisdicciones x censos 2001, 2010, 2022
    data/censos/departamentos.csv  todos los departamentos / partidos / comunas del país

Fuentes (todas INDEC, una por provincia):
  - Censo 2022, resultados definitivos, Cuadro 1.x: "Total de población ... por
    departamento. Años 2010 y 2022". Trae el código INDEC de cada departamento.
  - Censo 2010, Cuadro P1-P: "Población total y variación intercensal ... por
    departamento. Años 2001-2010". No trae códigos, solo nombres.

Cómo se unen: el valor de 2010 aparece en las dos publicaciones, así que cada fila
de 2001 se empareja con el departamento de 2022 que tiene la misma población 2010
dentro de la provincia (si hay empate, se desempata por nombre).

Controles (si alguno falla, termina con error y no escribe nada):
  - todas las filas 2001-2010 tienen par en 2022, y la población de 2010 coincide;
  - en cada provincia y censo, los departamentos suman el total provincial.

Uso:
    python scripts/construir_censos.py            # usa la caché de data/raw/indec/
    python scripts/construir_censos.py --forzar   # vuelve a descargar
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from popgrid_ar import config

INDEC = "https://www.indec.gob.ar"
CACHE = config.CRUDOS / "indec"
RUTA_2022 = "/ftp/cuadros/poblacion/"
RUTA_2010 = "/ftp/censos/2010/CuadrosDefinitivos/"

# Código de provincia -> (Cuadro 1.x del Censo 2022, Cuadro P1-P del Censo 2010).
CUADROS = {
    "02": ("c2022_caba_est_c1_1.xlsx", "P1-P_Caba.xls"),
    "06": ("c2022_bsas_est_c1_2.xlsx", "P1-P_Buenos_Aires.xls"),
    "10": ("c2022_catamarca_est_c1_3.xlsx", "P1-P_Catamarca.xls"),
    "14": ("c2022_cordoba_est_c1_6.xlsx", "P1-P_Cordoba.xls"),
    "18": ("c2022_corrientes_est_c1_7.xlsx", "P1-P_Corrientes.xls"),
    "22": ("c2022_chaco_est_c1_4.xlsx", "P1-P_Chaco.xls"),
    "26": ("c2022_chubut_est_c1_5.xlsx", "P1-P_Chubut.xls"),
    "30": ("c2022_entrerios_est_c1_8.xlsx", "P1-P_Entre_rios.xls"),
    "34": ("c2022_formosa_est_c1_9.xlsx", "P1-P_Formosa.xls"),
    "38": ("c2022_jujuy_est_c1_10.xlsx", "P1-P_Jujuy.xls"),
    "42": ("c2022_lapampa_est_c1_11.xlsx", "P1-P_La_pampa.xls"),
    "46": ("c2022_larioja_est_c1_12.xlsx", "P1-P_La_rioja.xls"),
    "50": ("c2022_mendoza_est_c1_13.xlsx", "P1-P_Mendoza.xls"),
    "54": ("c2022_misiones_est_c1_14.xlsx", "P1-P_Misiones.xls"),
    "58": ("c2022_neuquen_est_c1_15.xlsx", "P1-P_Neuquen.xls"),
    "62": ("c2022_rionegro_est_c1_16.xlsx", "P1-P_Rio_negro.xls"),
    "66": ("c2022_salta_est_c1_17.xlsx", "P1-P_Salta.xls"),
    "70": ("c2022_sanjuan_est_c1_18.xlsx", "P1-P_San_juan.xls"),
    "74": ("c2022_sanluis_est_c1_19.xlsx", "P1-P_San_luis.xls"),
    "78": ("c2022_santacruz_est_c1_20.xlsx", "P1-P_Santa_cruz.xls"),
    "82": ("c2022_santafe_est_c1_21.xlsx", "P1-P_Santa_fe.xls"),
    "86": ("c2022_santiago_est_c1_22.xlsx", "P1-P_Santiago_del_estero.xls"),
    "90": ("c2022_tucuman_est_c1_24.xlsx", "P1-P_Tucuman.xls"),
    "94": ("c2022_tdf_est_c1_23.xlsx", "P1-P_Tierra_del_fuego.xls"),
}
SIN_DATO = "///"


def _normalizar(texto) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def _entero(valor) -> int | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if str(valor).strip() == SIN_DATO:
        return None
    return int(round(float(valor)))


def descargar(ruta: str, archivo: str, forzar: bool) -> Path:
    destino = CACHE / archivo
    if destino.exists() and not forzar:
        return destino
    CACHE.mkdir(parents=True, exist_ok=True)
    r = requests.get(INDEC + ruta + archivo, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if not r.content.startswith((b"PK", b"\xd0\xcf\x11\xe0")):  # xlsx / xls
        raise ValueError(f"{archivo}: el INDEC no devolvió una planilla")
    destino.write_bytes(r.content)
    print(f"  descargado {archivo}")
    return destino


def leer_cuadro_2022(ruta: Path) -> tuple[dict[int, int], list[dict]]:
    """Devuelve ({2010: total, 2022: total}, [{codigo, nombre, 2010, 2022}, ...])."""
    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    cuadro = next(df for nombre, df in hojas.items() if nombre.lower().startswith("cuadro"))
    total, deptos = None, []
    for _, fila in cuadro.iterrows():
        codigo, nombre, p2010, p2022 = (fila.get(i) for i in range(4))
        if total is None and str(nombre).strip() == "Total":
            total = {2010: _entero(p2010), 2022: _entero(p2022)}
        elif re.fullmatch(r"\d{5}", str(codigo).strip()):
            deptos.append(
                {
                    "codigo": str(codigo).strip(),
                    "nombre": str(nombre).strip(),
                    2010: _entero(p2010),
                    2022: _entero(p2022),
                }
            )
    if total is None or not deptos:
        raise ValueError(f"{ruta.name}: formato inesperado")
    return total, deptos


def leer_cuadro_2001(ruta: Path) -> tuple[dict[int, int], list[dict]]:
    """Devuelve ({2001: total, 2010: total}, [{nombre, 2001, 2010}, ...])."""
    cuadro = pd.read_excel(ruta, header=None)
    total, filas = None, []
    for _, fila in cuadro.iterrows():
        nombre = fila.get(0)
        if isinstance(nombre, (int, float)) and not pd.isna(nombre):
            nombre = f"Comuna {int(nombre)}"  # CABA: el cuadro solo trae el número
        if not isinstance(nombre, str) or not nombre.strip() or nombre[0].isspace():
            continue  # vacías y subtotales indentados (p. ej. Antártida / Islas en TDF)
        try:
            p2001, p2010 = _entero(fila.get(1)), _entero(fila.get(2))
        except ValueError:
            continue  # encabezados y notas
        if p2010 is None:
            continue
        if nombre.strip() == "Total":
            total = {2001: p2001, 2010: p2010}
        else:
            filas.append({"nombre": nombre.strip(), 2001: p2001, 2010: p2010})
    if total is None or not filas:
        raise ValueError(f"{ruta.name}: formato inesperado")
    return total, filas


def unir(provincia: str, deptos_2022: list[dict], filas_2001: list[dict]) -> list[dict]:
    """Empareja cada fila 2001-2010 con un departamento 2022 por su población 2010."""
    por_2010: dict[int, list[dict]] = {}
    for d in deptos_2022:
        if d[2010] is not None:
            por_2010.setdefault(d[2010], []).append(d)
    usados = set()
    for fila in filas_2001:
        candidatos = [d for d in por_2010.get(fila[2010], []) if d["codigo"] not in usados]
        if len(candidatos) > 1:
            candidatos = [
                d for d in candidatos if _normalizar(d["nombre"]) == _normalizar(fila["nombre"])
            ]
        if len(candidatos) != 1:
            raise SystemExit(
                f"Provincia {provincia}: no se pudo emparejar '{fila['nombre']}' "
                f"(2010 = {fila[2010]}) con un departamento del Censo 2022"
            )
        depto = candidatos[0]
        depto[2001] = fila[2001]
        usados.add(depto["codigo"])
    return [
        {
            "codigo": d["codigo"],
            "provincia": config.PROVINCIAS[provincia],
            "nombre": d["nombre"],
            "pob_2001": d.get(2001),
            "pob_2010": d[2010],
            "pob_2022": d[2022],
        }
        for d in deptos_2022
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true", help="volver a descargar del INDEC")
    args = parser.parse_args()

    print("Leyendo cuadros del INDEC…")
    provincias, departamentos, errores = [], [], []
    for codigo, (arch_2022, arch_2001) in CUADROS.items():
        nombre = config.PROVINCIAS[codigo]
        total_22, deptos_22 = leer_cuadro_2022(descargar(RUTA_2022, arch_2022, args.forzar))
        total_01, filas_01 = leer_cuadro_2001(descargar(RUTA_2010, arch_2001, args.forzar))
        if total_01[2010] != total_22[2010]:
            errores.append(f"{nombre}: total 2010 difiere ({total_01[2010]} vs {total_22[2010]})")
        filas = unir(codigo, deptos_22, filas_01)
        for anio, total in ((2001, total_01[2001]), (2010, total_22[2010]), (2022, total_22[2022])):
            suma = sum(f[f"pob_{anio}"] or 0 for f in filas)
            if suma != total:
                errores.append(f"{nombre} {anio}: departamentos suman {suma}, total {total}")
        provincias.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "pob_2001": total_01[2001],
                "pob_2010": total_22[2010],
                "pob_2022": total_22[2022],
            }
        )
        departamentos += filas

    if errores:
        raise SystemExit("No se escribió nada:\n  " + "\n  ".join(errores))

    prov = pd.DataFrame(provincias)
    deptos = pd.DataFrame(departamentos).sort_values("codigo")
    for col in ("pob_2001", "pob_2010", "pob_2022"):
        deptos[col] = deptos[col].astype("Int64")

    config.CENSOS.mkdir(parents=True, exist_ok=True)
    prov.to_csv(config.CENSOS / "provincias.csv", index=False)
    deptos.to_csv(config.CENSOS / "departamentos.csv", index=False)

    print(f"  {len(prov)} provincias, {len(deptos)} departamentos")
    for anio in (2001, 2010, 2022):
        print(f"  {anio}: país {prov[f'pob_{anio}'].sum():>12,}")
    incompletos = deptos[deptos[["pob_2001", "pob_2010"]].isna().any(axis=1)]
    for _, d in incompletos.iterrows():
        print(f"  sin dato en algún censo: {d['codigo']} {d['nombre']} ({d['provincia']})")
    print("Listo: data/censos/provincias.csv y data/censos/departamentos.csv")


if __name__ == "__main__":
    main()
