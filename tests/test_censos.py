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

CENSOS_SALTA = [1869, 1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010, 2022]


CENSOS_PROVINCIAS = [1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010, 2022]


def test_provincias_valida():
    df = cargar_censo("provincias")
    assert df["codigo"].str.len().eq(2).all()
    assert censos_disponibles(df) == CENSOS_PROVINCIAS
    # 1895-1991 en % (INDEC, Cuadro 7); desde 2001, personas.
    cols = columnas_censo(df)
    assert all(cols[a].startswith("pct_") for a in CENSOS_PROVINCIAS[:7])
    assert all(cols[a].startswith("pob_") for a in CENSOS_PROVINCIAS[7:])


def test_provincias_historico_porcentajes():
    df = cargar_censo("provincias").set_index("codigo")
    # 1895: 2,2% sin jurisdicción determinada; 1914: 0,2%.
    assert df["pct_1895"].sum() == pytest.approx(97.8, abs=0.3)
    assert df["pct_1914"].sum() == pytest.approx(99.8, abs=0.3)
    # Tierra del Fuego < 0,05% hasta 1947 (se guarda como 0).
    assert (df.loc["94", ["pct_1895", "pct_1914", "pct_1947"]] == 0).all()
    assert df.loc["66", "pct_1895"] == 2.9  # Salta


def test_tabla_participacion_mezcla_porcentajes_y_personas():
    t = tabla_participacion(cargar_censo("provincias")).set_index("codigo")
    assert "pob_1895" not in t.columns and "pct_1895" in t.columns
    assert t["pct_2022"].sum() == pytest.approx(100, abs=0.1)
    assert "var_pp_1895_2022" in t.columns
    assert "crec_pct_2001_2022" in t.columns


def test_salta_historico_todos_los_censos_disponibles():
    df = cargar_censo("salta")
    assert list(columnas_censo(df)) == CENSOS_SALTA
    assert censos_disponibles(df) == CENSOS_SALTA


def test_salta_historico_coincide_con_indec_desde_2001():
    historico = cargar_censo("salta").set_index("codigo")
    indec = cargar_departamentos(config.CODIGO_SALTA).set_index("codigo")
    for anio in (2001, 2010, 2022):
        col = f"pob_{anio}"
        assert (historico.loc[indec.index, col] == indec[col]).all(), anio


def test_salta_historico_suma_el_total_provincial():
    historico = cargar_censo("salta")
    provincias = cargar_censo("provincias").set_index("codigo")
    for anio in (2001, 2010, 2022):
        assert historico[f"pob_{anio}"].sum() == provincias.loc["66", f"pob_{anio}"]


def test_salta_historico_oran_san_martin_y_los_andes():
    df = cargar_censo("salta").set_index("codigo")
    hasta_1947 = [f"pob_{a}" for a in (1869, 1895, 1914, 1947)]
    desde_1960 = [f"pob_{a}" for a in CENSOS_SALTA[4:]]
    # Orán y San Martín: juntos hasta 1947, separados desde 1960.
    assert df.loc["66126+66056", hasta_1947].notna().all()
    assert df.loc["66126+66056", desde_1960].isna().all()
    assert df.loc[["66126", "66056"], hasta_1947].isna().all().all()
    assert df.loc[["66126", "66056"], desde_1960].notna().all().all()
    # Los Andes: sin dato en 1869 y 1895.
    assert df.loc["66105", ["pob_1869", "pob_1895"]].isna().all()


def test_validar_detecta_doble_conteo():
    df = cargar_censo("salta").copy()
    df.loc[df["codigo"] == "66126", "pob_1947"] = 1  # Orán también dentro de la fila compuesta
    with pytest.raises(ValueError, match="dos veces"):
        validar(df, "salta")


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
