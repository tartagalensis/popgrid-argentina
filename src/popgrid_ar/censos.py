"""Lectura y validación de las tablas de población censal.

Las tablas viven en data/censos/ en formato ancho:

    provincias.csv       codigo,nombre,pob_2001,pob_2010,pob_2022          (INDEC)
    departamentos.csv    codigo,provincia,nombre,pob_2001,pob_2010,pob_2022 (INDEC)
    salta_historico.csv  codigo,nombre,pob_1869,...,pob_2022               (DGE Salta)

- `codigo` es el código INDEC (2 dígitos para provincias, 5 para departamentos)
  y se lee siempre como texto para no perder el cero inicial.
- Cada columna `pob_AAAA` es un censo.
- Una celda vacía significa que esa unidad no existía en ese censo.
- Una fila con código compuesto ("66126+66056") representa un departamento que
  después se dividió; en los censos en que tiene valor, sus partes van vacías.

Un censo es "disponible" para mapas cuando cada región esperada queda cubierta
exactamente una vez (directamente o por una fila compuesta), salvo las ausencias
declaradas en config (p. ej. Los Andes antes de 1914).
"""

from __future__ import annotations

import re

import pandas as pd

from . import config

ARCHIVO_PROVINCIAS = config.CENSOS / "provincias.csv"
ARCHIVO_DEPARTAMENTOS = config.CENSOS / "departamentos.csv"
ARCHIVO_SALTA_HISTORICO = config.CENSOS / "salta_historico.csv"
ARCHIVOS = {"provincias": ARCHIVO_PROVINCIAS, "salta": ARCHIVO_SALTA_HISTORICO}
CODIGOS_ESPERADOS = {
    "provincias": config.PROVINCIAS,
    "salta": config.DEPARTAMENTOS_SALTA,
}
AUSENCIAS = {"provincias": {}, "salta": config.AUSENCIAS_SALTA}
_PATRON_CENSO = re.compile(r"^pob_(\d{4})$")


def partes(codigo: str) -> list[str]:
    """Códigos actuales que representa una fila ('66126+66056' -> ['66126', '66056'])."""
    return codigo.split(config.SEPARADOR_COMPUESTO)


def cobertura(df: pd.DataFrame, anio: int) -> list[str]:
    """Códigos actuales cubiertos por las filas con dato en `anio` (con repeticiones)."""
    con_dato = df.loc[df[f"pob_{anio}"].notna(), "codigo"]
    return [c for codigo in con_dato for c in partes(codigo)]


def _faltantes(df: pd.DataFrame, nivel: str, anio: int) -> set[str]:
    ausentes = {c for c, anios in AUSENCIAS[nivel].items() if anio in anios}
    return set(CODIGOS_ESPERADOS[nivel]) - set(cobertura(df, anio)) - ausentes


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
    simples = {c for c in presentes if config.SEPARADOR_COMPUESTO not in c}
    if faltan := esperados - simples:
        problemas.append(f"faltan códigos: {sorted(faltan)}")
    if sobran := {p for c in presentes for p in partes(c)} - esperados:
        problemas.append(f"códigos desconocidos: {sorted(sobran)}")
    if not columnas_censo(df):
        problemas.append("no hay columnas pob_AAAA")
    for anio, col in columnas_censo(df).items():
        valores = df[col].dropna()
        if (valores <= 0).any():
            problemas.append(f"censo {anio}: hay valores <= 0")
        cubiertos = cobertura(df, anio)
        if len(cubiertos) != len(set(cubiertos)):
            problemas.append(f"censo {anio}: una región aparece contada dos veces")
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
    if nivel not in ARCHIVOS:
        raise ValueError(f"Nivel desconocido {nivel!r}; opciones: {config.NIVELES}")
    df = _leer(ARCHIVOS[nivel])
    validar(df, nivel)
    df.attrs["nivel"] = nivel
    return df


def censos_disponibles(df: pd.DataFrame, nivel: str | None = None) -> list[int]:
    """Años de censo en que todas las regiones esperadas tienen dato (salvo las
    ausencias declaradas). Sin `nivel` (o con un nivel desconocido), exige que la
    columna esté completa."""
    nivel = nivel or df.attrs.get("nivel")
    anios = columnas_censo(df)
    if nivel not in CODIGOS_ESPERADOS:
        return [a for a, col in anios.items() if df[col].notna().all()]
    return [a for a in anios if not _faltantes(df, nivel, a)]


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
