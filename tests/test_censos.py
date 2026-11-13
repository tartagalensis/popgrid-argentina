"""Tests de las tablas censales. No requieren red ni límites descargados."""

import pandas as pd
import pytest

from popgrid_ar import config
from popgrid_ar.censos import (
    cargar_censo,
    cargar_departamentos,
    censos_disponibles,
    columnas_censo,
    tabla_participacion,
    validar,
)


@pytest.mark.parametrize("nivel", config.NIVELES)
def test_tablas_reales_son_validas(nivel):
    df = cargar_censo(nivel)
    assert df["codigo"].str.len().eq(2 if nivel == "provincias" else 5).all()
    assert list(columnas_censo(df)) == [2001, 2010, 2022]


def test_censos_completos_para_mapas():
    assert censos_disponibles(cargar_censo("provincias")) == [2001, 2010, 2022]
    assert censos_disponibles(cargar_censo("salta")) == [2001, 2010, 2022]


def test_departamentos_suman_el_total_de_cada_provincia():
    provincias = cargar_censo("provincias").set_index("codigo")
    deptos = cargar_departamentos()
    deptos["prov"] = deptos["codigo"].str[:2]
    assert set(deptos["prov"]) == set(config.PROVINCIAS)
    for anio in (2001, 2010, 2022):
        sumas = deptos.groupby("prov")[f"pob_{anio}"].sum()
        assert (sumas == provincias[f"pob_{anio}"]).all(), anio


def test_departamentos_sin_dato_solo_los_creados_despues_de_2010():
    deptos = cargar_departamentos()
    incompletos = deptos[deptos[["pob_2001", "pob_2010"]].isna().any(axis=1)]
    assert set(incompletos["codigo"]) == {"06466", "94011"}  # Lezama, Tolhuin
    assert deptos["pob_2022"].notna().all()


def test_cargar_departamentos_filtra_por_provincia():
    salta = cargar_departamentos(config.CODIGO_SALTA)
    assert set(salta["codigo"]) == set(config.DEPARTAMENTOS_SALTA)
    with pytest.raises(ValueError):
        cargar_departamentos("99")


def _tabla(valores_2001, valores_2022):
    return pd.DataFrame(
        {
            "codigo": list(config.DEPARTAMENTOS_SALTA),
            "nombre": list(config.DEPARTAMENTOS_SALTA.values()),
            "pob_2001": pd.array(valores_2001, dtype="Int64"),
            "pob_2022": pd.array(valores_2022, dtype="Int64"),
        }
    )


def test_validar_detecta_codigo_faltante():
    df = _tabla([100] * 23, [100] * 23).iloc[1:]
    with pytest.raises(ValueError, match="faltan códigos"):
        validar(df, "salta")


def test_validar_detecta_valores_no_positivos():
    df = _tabla([0] + [100] * 22, [100] * 23)
    with pytest.raises(ValueError, match="<= 0"):
        validar(df, "salta")


def test_censos_disponibles_ignora_censos_incompletos():
    df = _tabla([None] + [100] * 22, [100] * 23)
    assert censos_disponibles(df) == [2022]


def test_tabla_participacion():
    df = _tabla([100] * 23, [200] + [100] * 22)
    t = tabla_participacion(df)
    assert t["pct_2001"].sum() == pytest.approx(100, abs=0.1)
    assert t["pct_2022"].sum() == pytest.approx(100, abs=0.1)
    assert t.loc[0, "crec_pct_2001_2022"] == 100.0
    assert t.loc[0, "var_pp_2001_2022"] > 0
    assert (t.loc[1:, "var_pp_2001_2022"] < 0).all()
