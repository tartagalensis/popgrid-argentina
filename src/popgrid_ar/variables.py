"""Variables que se pueden mapear: población y exportaciones.

Pendiente: PBI (ver README, sección Pendientes).

En un mapa de bloques, cada bloque es una porción fija del total de la variable
(con n=1000, el 0,1%). Solo sirven variables que se suman entre regiones.

Columnas en los CSV: pob_AAAA (personas), pct_AAAA (% publicado) y val_AAAA
(monto de una variable económica). Ver popgrid_ar.censos.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from . import config


@dataclass(frozen=True)
class Variable:
    clave: str
    titulo: str  # "Población"
    nombre: str  # "población" (para "superficie y población por censo")
    de: str  # "de la población" (para "Cada bloque = 0,1% de la población del país")
    periodo: str  # "censo" | "año"
    fuente: str  # texto corto para el pie
    unidad: str  # unidad de los valores
    # Archivos por tipo de nivel base (None si la variable no existe a ese nivel).
    archivo_provincias: str | None = None
    archivo_departamentos: str | None = None
    provisorios: tuple[int, ...] = ()

    def etiqueta(self, anio: int) -> str:
        """'Censo 2022' o '2022'."""
        return f"Censo {anio}" if self.periodo == "censo" else str(anio)

    def anios_por_defecto(self, disponibles: list[int]) -> list[int]:
        """Para series largas (anuales), el primer año, los múltiplos de 5 y el último."""
        if len(disponibles) <= 11:
            return disponibles
        elegidos = {disponibles[0], disponibles[-1]} | {a for a in disponibles if a % 5 == 0}
        return sorted(elegidos)

    def sin_provincia_pct(self, anio: int) -> float | None:
        """% del total del país que no tiene provincia asignada en ese año."""
        if self.clave == "poblacion":
            return config.SIN_JURISDICCION_PCT.get(anio)
        if self.clave == "exportaciones":
            otros = _exportaciones_otros()
            col = f"val_{anio}"
            if col not in otros.columns:
                return None
            sin = otros.loc[["Extranjero y plataforma continental", "Indeterminado"], col].sum()
            return float(sin / otros.loc["Total", col] * 100)
        return None


@cache
def _exportaciones_otros() -> pd.DataFrame:
    return pd.read_csv(config.ECONOMIA / "exportaciones_otros.csv").set_index("concepto")


VARIABLES = {
    "poblacion": Variable(
        clave="poblacion",
        titulo="Población",
        nombre="población",
        de="de la población",
        periodo="censo",
        fuente="Población: INDEC, censos nacionales",
        unidad="personas",
    ),
    "exportaciones": Variable(
        clave="exportaciones",
        titulo="Exportaciones",
        nombre="exportaciones",
        de="de las exportaciones",
        periodo="año",
        fuente="Exportaciones: INDEC, Origen provincial de las exportaciones (OPEX)",
        unidad="millones de USD corrientes",
        archivo_provincias="exportaciones_provincias.csv",
        provisorios=(2024, 2025),
    ),
}


def variable(clave: str | Variable) -> Variable:
    if isinstance(clave, Variable):
        return clave
    if clave not in VARIABLES:
        raise ValueError(f"Variable desconocida {clave!r}; opciones: {sorted(VARIABLES)}")
    return VARIABLES[clave]
