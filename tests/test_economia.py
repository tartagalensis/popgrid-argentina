"""Tests de variables económicas (exportaciones). Sin red."""

import pandas as pd
import pytest

from popgrid_ar import config
from popgrid_ar.censos import cargar_censo, censos_disponibles
from popgrid_ar.mapas import _agrupar_notas
from popgrid_ar.variables import variable

ANIOS = list(range(1993, 2026))


def test_exportaciones_por_provincia():
    df = cargar_censo("provincias", "exportaciones")
    assert set(df["codigo"]) == set(config.PROVINCIAS)
    assert censos_disponibles(df) == ANIOS


def test_exportaciones_cierran_con_el_total_del_indec():
    prov = pd.read_csv(config.ECONOMIA / "exportaciones_provincias.csv", dtype={"codigo": str})
    otros = pd.read_csv(config.ECONOMIA / "exportaciones_otros.csv").set_index("concepto")
    for a in ANIOS:
        col = f"val_{a}"
        suma = (
            prov[col].sum()
            + otros.loc[["Extranjero y plataforma continental", "Indeterminado"], col].sum()
        )
        assert suma == pytest.approx(otros.loc["Total", col], rel=1e-3, abs=1), a


def test_exportaciones_por_zona_suman_las_provincias():
    z = cargar_censo("zonas:argentina", "exportaciones")
    p = cargar_censo("provincias", "exportaciones")
    for a in ANIOS:
        assert float(z[f"val_{a}"].sum()) == pytest.approx(float(p[f"val_{a}"].sum()))


def test_exportaciones_no_existen_por_departamento():
    with pytest.raises(ValueError, match="no está disponible"):
        cargar_censo("salta", "exportaciones")


def test_sin_provincia_y_provisorios():
    exp = variable("exportaciones")
    assert exp.sin_provincia_pct(2022) == pytest.approx(1.5, abs=0.1)
    assert exp.provisorios == (2024, 2025)
    assert variable("poblacion").sin_provincia_pct(1895) == 2.2
    assert exp.anios_por_defecto(ANIOS) == [1993, 1995, 2000, 2005, 2010, 2015, 2020, 2025]


def test_agrupar_notas_resume_series_largas():
    notas = {
        f"{v}% de las exportaciones sin provincia asignada": [a]
        for a, v in zip(range(2000, 2006), ["1,5", "2,0", "6,2", "3,0", "4,0", "2,5"], strict=True)
    }
    notas["datos provisorios"] = [2005]
    salida = _agrupar_notas(notas, list(range(2000, 2006)))
    assert salida[0] == (
        "% de las exportaciones sin provincia asignada: entre 1,5% y 6,2% según el año (2000-2005)"
    )
    assert salida[1] == "2005: datos provisorios"
