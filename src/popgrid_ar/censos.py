"""Lectura y validación de las tablas de población censal.

Las tablas viven en data/censos/ en formato ancho:

    provincias.csv            codigo,nombre,pob_2001,pob_2010,pob_2022          (INDEC)
    provincias_historico.csv  codigo,nombre,pct_1895,...,pct_1991               (INDEC, %)
    departamentos.csv         codigo,provincia,nombre,pob_2001,pob_2010,pob_2022 (INDEC)
    salta_historico.csv       codigo,nombre,pob_1869,...,pob_2022               (DGE Salta)

- `codigo` es el código INDEC (2 dígitos para provincias, 5 para departamentos)
  y se lee siempre como texto para no perder el cero inicial. En el nivel de zonas,
  el código es el nombre de la zona en minúsculas ("valle_de_lerma").
- Cada columna `pob_AAAA` (personas) o `pct_AAAA` (% publicado) es un censo.
- Una celda vacía significa que esa unidad no existía en ese censo.
- Una fila con código compuesto ("66126+66056") representa un departamento que
  después se dividió; en los censos en que tiene valor, sus partes van vacías.

Un censo es "disponible" para mapas cuando cada región esperada queda cubierta
exactamente una vez (directamente o por una fila compuesta), salvo las ausencias
declaradas (p. ej. Los Andes antes de 1914).
"""

from __future__ import annotations

import re

import pandas as pd

from . import config
from .niveles import Nivel, zonas
from .niveles import nivel as obtener_nivel
from .variables import Variable
from .variables import variable as obtener_variable

ARCHIVO_PROVINCIAS = config.CENSOS / "provincias.csv"
ARCHIVO_DEPARTAMENTOS = config.CENSOS / "departamentos.csv"
ARCHIVO_PROVINCIAS_HISTORICO = config.CENSOS / "provincias_historico.csv"
ARCHIVO_SALTA_HISTORICO = config.CENSOS / "salta_historico.csv"
# pob_AAAA: personas (exacto). pct_AAAA: % del total publicado con un decimal
# (provincias 1895-1991, INDEC solo publica porcentajes). Si hay ambos, manda pob.
_PATRON_CENSO = re.compile(r"^(pob|pct|val)_(\d{4})$")


def _nivel(nivel: str | Nivel) -> Nivel:
    return nivel if isinstance(nivel, Nivel) else obtener_nivel(nivel)


def partes(codigo: str) -> list[str]:
    """Códigos actuales que representa una fila ('66126+66056' -> ['66126', '66056'])."""
    return codigo.split(config.SEPARADOR_COMPUESTO)


def columnas_censo(df: pd.DataFrame) -> dict[int, str]:
    """Devuelve {año: columna} para cada columna `pob_AAAA` o `pct_AAAA`."""
    salida: dict[int, str] = {}
    for col in df.columns:
        m = _PATRON_CENSO.match(col)
        if m and (int(m.group(2)) not in salida or m.group(1) != "pct"):
            salida[int(m.group(2))] = col
    return dict(sorted(salida.items()))


def columna(df: pd.DataFrame, anio: int) -> str:
    """Nombre de la columna que tiene el dato de `anio` (pob_AAAA o pct_AAAA)."""
    return columnas_censo(df)[anio]


def es_porcentaje(col: str) -> bool:
    return col.startswith("pct_")


def cobertura(df: pd.DataFrame, anio: int) -> list[str]:
    """Códigos actuales cubiertos por las filas con dato en `anio` (con repeticiones)."""
    con_dato = df.loc[df[columna(df, anio)].notna(), "codigo"]
    return [c for codigo in con_dato for c in partes(codigo)]


def _faltantes(df: pd.DataFrame, n: Nivel, anio: int) -> set[str]:
    ausentes = {c for c, anios in n.ausencias.items() if anio in anios}
    return set(n.nombres) - set(cobertura(df, anio)) - ausentes


def validar(df: pd.DataFrame, nivel: str | Nivel) -> None:
    """Verifica códigos y valores. Lanza ValueError con todos los problemas."""
    n = _nivel(nivel)
    problemas = []
    esperados = set(n.nombres)
    presentes = list(df["codigo"])
    if len(presentes) != len(set(presentes)):
        problemas.append("hay códigos repetidos")
    simples = {c for c in presentes if config.SEPARADOR_COMPUESTO not in c}
    if faltan := esperados - simples:
        problemas.append(f"faltan códigos: {sorted(faltan)}")
    if sobran := {p for c in presentes for p in partes(c)} - esperados:
        problemas.append(f"códigos desconocidos: {sorted(sobran)}")
    if not columnas_censo(df):
        problemas.append("no hay columnas pob_AAAA ni pct_AAAA")
    for anio, col in columnas_censo(df).items():
        valores = df[col].dropna()
        if es_porcentaje(col):
            # 0 = menos de 0,05% (el cuadro publica 0,0 o "–"). La suma puede quedar
            # debajo de 100: en 1895 hay un 2,2% sin jurisdicción determinada.
            if (valores < 0).any() or not 97 <= valores.sum() <= 101:
                problemas.append(f"censo {anio}: porcentajes fuera de rango")
        elif col.startswith("val_"):
            # Montos económicos: 0 es válido (una región puede no exportar).
            if (valores < 0).any():
                problemas.append(f"{anio}: hay valores negativos")
        elif (valores <= 0).any():
            problemas.append(f"censo {anio}: hay valores <= 0")
        cubiertos = cobertura(df, anio)
        if len(cubiertos) != len(set(cubiertos)):
            problemas.append(f"censo {anio}: una región aparece contada dos veces")
    if problemas:
        raise ValueError(f"{n.clave}: " + "; ".join(problemas))


def _leer(ruta) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype={"codigo": str})
    for col in df.columns:
        if _PATRON_CENSO.match(col):
            tipo = "Int64" if col.startswith("pob_") else "Float64"
            df[col] = pd.to_numeric(df[col], errors="raise").astype(tipo)
    return df


def cargar_departamentos(provincia: str | None = None) -> pd.DataFrame:
    """Tabla de todos los departamentos del país (INDEC, 2001-2022), o de una
    provincia si se pasa su código INDEC de 2 dígitos (p. ej. '66' para Salta)."""
    df = _leer(ARCHIVO_DEPARTAMENTOS)
    if df["codigo"].duplicated().any():
        raise ValueError(f"{ARCHIVO_DEPARTAMENTOS.name}: hay códigos repetidos")
    if provincia is not None:
        if provincia not in config.PROVINCIAS:
            raise ValueError(f"Código de provincia desconocido: {provincia!r}")
        df = df[df["codigo"].str.startswith(provincia)].reset_index(drop=True)
    return df


def _con_contenidos(df: pd.DataFrame) -> pd.DataFrame:
    """Departamentos creados después de un censo (config.CONTENIDOS): en los censos
    en que su población está dentro de otro, se agrega una fila compuesta
    'origen+nuevo' con el valor del origen, y el origen queda vacío esos años."""
    df = df.copy()
    nuevas = []
    for nuevo, (origen, anios) in config.CONTENIDOS.items():
        if not {nuevo, origen} <= set(df["codigo"]):
            continue
        fila_origen = df.index[df["codigo"] == origen][0]
        nombre_nuevo = df.loc[df["codigo"] == nuevo, "nombre"].iloc[0]
        compuesta = {
            "codigo": f"{origen}{config.SEPARADOR_COMPUESTO}{nuevo}",
            "nombre": f"{df.at[fila_origen, 'nombre']} (incl. {nombre_nuevo})",
        }
        for anio, col in columnas_censo(df).items():
            if anio in anios:
                compuesta[col] = df.at[fila_origen, col]
                df.at[fila_origen, col] = pd.NA
            else:
                compuesta[col] = pd.NA
        nuevas.append(compuesta)
    if nuevas:
        df = pd.concat([df, pd.DataFrame(nuevas).astype(df.dtypes.to_dict())], ignore_index=True)
    return df


def _agrupar_zonas(deptos: pd.DataFrame, n: Nivel) -> pd.DataFrame:
    """Suma las regiones del nivel base (departamentos o provincias) por zona."""
    tabla = zonas(n.zonas_de)
    zona_de = dict(zip(tabla["codigo"], tabla["zona"], strict=True))
    asignadas = []
    for codigo in deptos["codigo"]:
        zonas_fila = {zona_de[p] for p in partes(codigo)}
        if len(zonas_fila) != 1:
            raise ValueError(
                f"{codigo} junta regiones de zonas distintas ({sorted(zonas_fila)}): "
                "no se puede repartir su población"
            )
        asignadas.append(zonas_fila.pop())
    cols = list(columnas_censo(deptos).values())
    sumas = deptos.assign(zona=asignadas).groupby("zona", sort=False)[cols].sum(min_count=1)
    orden = list(n.nombres.values())
    sumas = sumas.reindex(orden)
    salida = pd.DataFrame({"codigo": list(n.nombres), "nombre": orden})
    for col in cols:
        salida[col] = sumas[col].to_numpy()
        salida[col] = salida[col].astype(deptos[col].dtype)
    return salida


def _cargar_economia(n: Nivel, var: Variable) -> pd.DataFrame:
    """Variables económicas: se leen por provincia o por departamento y se
    agrupan en zonas igual que la población."""
    if n.tipo == "zonas":
        return _agrupar_zonas(cargar_censo(n.base, var), n)
    archivo = var.archivo_provincias if n.tipo == "provincias" else var.archivo_departamentos
    if archivo is None:
        raise ValueError(f"{var.titulo} no está disponible por {n.tipo}")
    df = _leer(config.ECONOMIA / archivo)
    return df[df["codigo"].isin(n.nombres)].reset_index(drop=True)[
        ["codigo", "nombre", *columnas_censo(df).values()]
    ]


def cargar_censo(nivel: str | Nivel, variable: str | Variable = "poblacion") -> pd.DataFrame:
    """Lee y valida la tabla de un nivel ('provincias', 'salta',
    'departamentos:<provincia>', 'zonas:<provincia>') para una variable
    ('poblacion', 'exportaciones', 'pbi')."""
    n = _nivel(nivel)
    var = obtener_variable(variable)
    if var.clave != "poblacion":
        df = _cargar_economia(n, var)
    elif n.tipo == "provincias":
        df = _leer(ARCHIVO_PROVINCIAS)
        if ARCHIVO_PROVINCIAS_HISTORICO.exists():
            historico = _leer(ARCHIVO_PROVINCIAS_HISTORICO).drop(columns="nombre")
            df = historico.merge(df, on="codigo", how="right", validate="1:1")
            df = df[["codigo", "nombre", *columnas_censo(df).values()]]
    elif n.tipo == "departamentos":
        if n.provincia == config.CODIGO_SALTA:
            df = _leer(ARCHIVO_SALTA_HISTORICO)
        else:
            df = cargar_departamentos(n.provincia).drop(columns="provincia")
            df = df[df["codigo"].isin(n.nombres)].reset_index(drop=True)
            df = _con_contenidos(df)
    else:
        df = _agrupar_zonas(cargar_censo(n.base), n)
    validar(df, n)
    df.attrs["nivel"] = n.clave
    df.attrs["variable"] = var.clave
    return df


def censos_disponibles(df: pd.DataFrame, nivel: str | Nivel | None = None) -> list[int]:
    """Años de censo en que todas las regiones esperadas tienen dato (salvo las
    ausencias declaradas). Sin nivel conocido, exige que la columna esté completa."""
    clave = nivel or df.attrs.get("nivel")
    anios = columnas_censo(df)
    if clave is None:
        return [a for a, col in anios.items() if df[col].notna().all()]
    n = _nivel(clave)
    return [a for a in anios if not _faltantes(df, n, a)]


def tabla_participacion(df: pd.DataFrame) -> pd.DataFrame:
    """Participación (%) de cada fila en el total de cada censo disponible, la
    variación en puntos porcentuales entre el primer y el último censo, y el
    crecimiento (%) entre el primer y el último censo con cantidades exactas.
    Para los censos que solo tienen porcentaje publicado, se usa ese valor.
    """
    anios = censos_disponibles(df)
    salida = df[["codigo", "nombre"]].copy()
    con_personas = []
    for anio in anios:
        col = columna(df, anio)
        if es_porcentaje(col):
            salida[f"pct_{anio}"] = df[col].astype(float)
        else:
            con_personas.append(anio)
            salida[col] = df[col]
            salida[f"pct_{anio}"] = (df[col] / df[col].sum() * 100).astype(float).round(2)
    if len(anios) >= 2:
        primero, ultimo = anios[0], anios[-1]
        salida[f"var_pp_{primero}_{ultimo}"] = (
            salida[f"pct_{ultimo}"] - salida[f"pct_{primero}"]
        ).round(2)
    if len(con_personas) >= 2:
        primero, ultimo = con_personas[0], con_personas[-1]
        salida[f"crec_pct_{primero}_{ultimo}"] = (
            ((df[f"pob_{ultimo}"] / df[f"pob_{primero}"] - 1) * 100).astype(float).round(1)
        )
    return salida
