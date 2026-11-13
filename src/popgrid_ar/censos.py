"""Lectura y validación de las tablas de población censal.

Las tablas viven en data/censos/ en formato ancho y las genera
scripts/construir_censos.py a partir de los cuadros del INDEC:

    provincias.csv     codigo,nombre,pob_2001,pob_2010,pob_2022
    departamentos.csv  codigo,provincia,nombre,pob_2001,pob_2010,pob_2022

- `codigo` es el código INDEC (2 dígitos para provincias, 5 para departamentos)
  y se lee siempre como texto para no perder el cero inicial.
- Cada columna `pob_AAAA` es un censo.
- Una celda vacía significa que el departamento no existía en ese censo
  (p. ej. Lezama y Tolhuin antes de 2022). Un censo solo se usa para mapas si
  está completo para todas las filas del nivel elegido.
"""

from __future__ import annotations

import re

import pandas as pd

from . import config

ARCHIVO_PROVINCIAS = config.CENSOS / "provincias.csv"
ARCHIVO_DEPARTAMENTOS = config.CENSOS / "departamentos.csv"
ARCHIVOS = {"provincias": ARCHIVO_PROVINCIAS, "salta": ARCHIVO_DEPARTAMENTOS}
CODIGOS_ESPERADOS = {
    "provincias": config.PROVINCIAS,
    "salta": config.DEPARTAMENTOS_SALTA,
}
_PATRON_CENSO = re.compile(r"^pob_(\d{4})$")


def columnas_censo(df: pd.DataFrame) -> dict[int, str]:
    """Devuelve {año: columna} para cada columna `pob_AAAA`."""
    salida = {}
    for col in df.columns:
        m = _PATRON_CENSO.match(col)
        if m:
            salida[int(m.group(1))] = col
    return dict(sorted(salida.items()))


def validar(df: pd.DataFrame, nivel: str) -> None:
    """Verifica códigos y valores. Lanza ValueError con todos los problemas."""
    problemas = []
    esperados = set(CODIGOS_ESPERADOS[nivel])
    presentes = list(df["codigo"])
    if len(presentes) != len(set(presentes)):
        problemas.append("hay códigos repetidos")
    if faltan := esperados - set(presentes):
        problemas.append(f"faltan códigos: {sorted(faltan)}")
    if sobran := set(presentes) - esperados:
        problemas.append(f"códigos desconocidos: {sorted(sobran)}")
    if not columnas_censo(df):
        problemas.append("no hay columnas pob_AAAA")
    for anio, col in columnas_censo(df).items():
        valores = df[col].dropna()
        if (valores <= 0).any():
            problemas.append(f"censo {anio}: hay valores <= 0")
    if problemas:
        raise ValueError(f"{ARCHIVOS[nivel].name}: " + "; ".join(problemas))


def _leer(ruta) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype={"codigo": str})
    for col in columnas_censo(df).values():
        df[col] = pd.to_numeric(df[col], errors="raise").astype("Int64")
    return df


def cargar_departamentos(provincia: str | None = None) -> pd.DataFrame:
    """Tabla de todos los departamentos del país, o de una provincia si se pasa
    su código INDEC de 2 dígitos (p. ej. '66' para Salta)."""
    df = _leer(ARCHIVO_DEPARTAMENTOS)
    if df["codigo"].duplicated().any():
        raise ValueError(f"{ARCHIVO_DEPARTAMENTOS.name}: hay códigos repetidos")
    if provincia is not None:
        if provincia not in config.PROVINCIAS:
            raise ValueError(f"Código de provincia desconocido: {provincia!r}")
        df = df[df["codigo"].str.startswith(provincia)].reset_index(drop=True)
    return df


def cargar_censo(nivel: str) -> pd.DataFrame:
    """Lee y valida la tabla censal de `nivel` ('provincias' o 'salta')."""
    if nivel == "provincias":
        df = _leer(ARCHIVO_PROVINCIAS)
    elif nivel == "salta":
        df = cargar_departamentos(config.CODIGO_SALTA).drop(columns="provincia")
    else:
        raise ValueError(f"Nivel desconocido {nivel!r}; opciones: {config.NIVELES}")
    validar(df, nivel)
    return df


def censos_disponibles(df: pd.DataFrame) -> list[int]:
    """Años de censo con datos completos (sin celdas vacías)."""
    return [anio for anio, col in columnas_censo(df).items() if df[col].notna().all()]


def tabla_participacion(df: pd.DataFrame) -> pd.DataFrame:
    """Participación (%) de cada fila en el total de cada censo completo,
    más la variación en puntos porcentuales entre el primer y el último censo.
    """
    anios = censos_disponibles(df)
    salida = df[["codigo", "nombre"]].copy()
    for anio in anios:
        col = f"pob_{anio}"
        salida[col] = df[col]
        salida[f"pct_{anio}"] = (df[col] / df[col].sum() * 100).astype(float).round(2)
    if len(anios) >= 2:
        primero, ultimo = anios[0], anios[-1]
        salida[f"var_pp_{primero}_{ultimo}"] = (
            salida[f"pct_{ultimo}"] - salida[f"pct_{primero}"]
        ).round(2)
        salida[f"crec_pct_{primero}_{ultimo}"] = (
            ((df[f"pob_{ultimo}"] / df[f"pob_{primero}"] - 1) * 100).astype(float).round(1)
        )
    return salida
