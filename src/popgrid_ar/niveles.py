"""Niveles de análisis: qué regiones se comparan y de dónde salen sus datos.

Claves aceptadas:
    "provincias"                  24 jurisdicciones (1895-2022)
    "departamentos:<provincia>"   departamentos de una provincia (Salta: 1869-2022;
                                  el resto: 2001-2022)
    "zonas:<provincia>"           departamentos agrupados según data/zonas/<provincia>.csv
    "zonas:argentina"             provincias agrupadas según data/zonas/argentina.csv (1895-2022)
    "salta"                       atajo de "departamentos:66"

<provincia> puede ser el código INDEC ("66") o el nombre ("salta", "Tierra del Fuego").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache

import pandas as pd

from . import config

ATAJOS = {"salta": "departamentos:66"}


def slug(texto: str) -> str:
    """'Tierra del Fuego' -> 'tierra_del_fuego'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")


def codigo_provincia(texto: str) -> str:
    if texto in config.PROVINCIAS:
        return texto
    por_slug = {slug(n): c for c, n in config.PROVINCIAS.items()}
    if slug(texto) in por_slug:
        return por_slug[slug(texto)]
    raise ValueError(f"Provincia desconocida: {texto!r}")


@dataclass(frozen=True)
class Nivel:
    clave: str  # forma canónica: "provincias", "departamentos:66", "zonas:66"
    tipo: str  # "provincias" | "departamentos" | "zonas"
    provincia: str | None  # código INDEC de 2 dígitos
    nombres: dict[str, str] = field(hash=False)  # regiones actuales: código -> nombre
    ausencias: dict[str, tuple[int, ...]] = field(hash=False)  # código -> censos sin la región
    base: str | None = None  # zonas: clave del nivel que se agrupa
    zonas_de: str | None = None  # zonas: nombre del archivo en data/zonas/ (sin .csv)

    @property
    def nombre_provincia(self) -> str:
        return config.PROVINCIAS[self.provincia] if self.provincia else "Argentina"

    @property
    def titulo(self) -> str:
        if self.tipo == "zonas":
            return f"{self.nombre_provincia} por zonas"
        return self.nombre_provincia

    @property
    def territorio(self) -> str:
        """Nombre del territorio para las notas ('aún no integraba Salta')."""
        return self.nombre_provincia

    @property
    def unidad(self) -> str:
        return "del país" if self.provincia is None else "de la provincia"

    @property
    def archivo(self) -> str:
        """Prefijo para los archivos de salida."""
        if self.tipo == "provincias":
            return "provincias"
        base = slug(self.nombre_provincia)
        return f"{base}_zonas" if self.tipo == "zonas" else base

    @property
    def fuente(self) -> str:
        if self.provincia == config.CODIGO_SALTA:
            return (
                "Límites: IGN · Población: INDEC, censos nacionales "
                "(serie de la DGE Salta) · popgrid"
            )
        return "Límites: IGN · Población: INDEC, censos nacionales · popgrid"


def archivo_zonas(nombre: str):
    return config.ZONAS / f"{nombre}.csv"


@cache
def zonas(nombre: str) -> pd.DataFrame:
    """Tabla codigo -> zona (data/zonas/<nombre>.csv: 'salta', 'argentina', ...)."""
    ruta = archivo_zonas(nombre)
    if not ruta.exists():
        raise FileNotFoundError(f"No hay zonas definidas: falta {ruta}")
    df = pd.read_csv(ruta, dtype={"codigo": str})
    if df["codigo"].duplicated().any():
        raise ValueError(f"{ruta.name}: hay códigos repetidos")
    return df


@cache
def _departamentos(provincia: str) -> dict[str, str]:
    """Departamentos actuales de una provincia (código -> nombre), sin los excluidos."""
    if provincia == config.CODIGO_SALTA:
        return dict(config.DEPARTAMENTOS_SALTA)
    tabla = pd.read_csv(config.CENSOS / "departamentos.csv", dtype={"codigo": str})
    tabla = tabla[tabla["codigo"].str.startswith(provincia)]
    tabla = tabla[~tabla["codigo"].isin(config.DEPARTAMENTOS_EXCLUIDOS)]
    return dict(zip(tabla["codigo"], tabla["nombre"], strict=True))


def nivel(clave: str) -> Nivel:
    """Interpreta una clave de nivel ('provincias', 'salta', 'zonas:66', ...)."""
    clave = ATAJOS.get(clave, clave)
    if clave == "provincias":
        return Nivel("provincias", "provincias", None, dict(config.PROVINCIAS), {})
    tipo, _, prov = clave.partition(":")
    if tipo not in ("departamentos", "zonas") or not prov:
        raise ValueError(
            f"Nivel desconocido {clave!r}: usá 'provincias', 'departamentos:<provincia>' "
            "o 'zonas:<provincia>'"
        )
    if tipo == "zonas" and slug(prov) == "argentina":
        base = nivel("provincias")
        prov, archivo = None, "argentina"
    else:
        prov = codigo_provincia(prov)
        ausencias_deptos = config.AUSENCIAS_SALTA if prov == config.CODIGO_SALTA else {}
        base = Nivel(
            f"departamentos:{prov}",
            "departamentos",
            prov,
            _departamentos(prov),
            dict(ausencias_deptos),
        )
        archivo = slug(config.PROVINCIAS[prov])
    if tipo == "departamentos":
        return base

    tabla = zonas(archivo)
    if faltan := set(base.nombres) - set(tabla["codigo"]):
        raise ValueError(f"{archivo}.csv: faltan códigos {sorted(faltan)}")
    if sobran := set(tabla["codigo"]) - set(base.nombres):
        raise ValueError(f"{archivo}.csv: códigos desconocidos {sorted(sobran)}")
    nombres = {slug(z): z for z in dict.fromkeys(tabla["zona"])}
    # Una zona falta en un censo solo si faltan todas sus regiones.
    ausencias = {}
    for z_slug, z in nombres.items():
        miembros = tabla.loc[tabla["zona"] == z, "codigo"]
        anios = [set(base.ausencias.get(c, ())) for c in miembros]
        if comunes := set.intersection(*anios):
            ausencias[z_slug] = tuple(sorted(comunes))
    return Nivel(
        f"zonas:{prov or archivo}",
        "zonas",
        prov,
        nombres,
        ausencias,
        base=base.clave,
        zonas_de=archivo,
    )
