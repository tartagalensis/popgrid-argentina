"""Tests de niveles: departamentos de cualquier provincia y zonas. Sin red."""

import pandas as pd
import pytest

from popgrid_ar import config
from popgrid_ar.censos import cargar_censo, censos_disponibles, columna
from popgrid_ar.niveles import nivel, zonas


@pytest.mark.parametrize(
    ("clave", "canonica"),
    [
        ("salta", "departamentos:66"),
        ("departamentos:Salta", "departamentos:66"),
        ("departamentos:tierra del fuego", "departamentos:94"),
        ("zonas:salta", "zonas:66"),
        ("zonas:argentina", "zonas:argentina"),
        ("provincias", "provincias"),
    ],
)
def test_claves(clave, canonica):
    assert nivel(clave).clave == canonica


def test_clave_invalida():
    with pytest.raises(ValueError):
        nivel("municipios:66")
    with pytest.raises(ValueError):
        nivel("departamentos:narnia")


@pytest.mark.parametrize("prov", sorted(config.PROVINCIAS))
def test_departamentos_de_todas_las_provincias(prov):
    df = cargar_censo(f"departamentos:{prov}")
    esperados = [2001, 2010, 2022] if prov != config.CODIGO_SALTA else None
    disponibles = censos_disponibles(df)
    if esperados:
        assert disponibles == esperados
    total = cargar_censo("provincias").set_index("codigo")
    if prov != "94":  # TDF: los mapas excluyen Antártida e Islas del Atlántico Sur
        for anio in (2001, 2010, 2022):
            assert df[columna(df, anio)].sum() == total.loc[prov, f"pob_{anio}"]


def test_lezama_y_tolhuin_dentro_de_su_origen():
    ba = cargar_censo("departamentos:06").set_index("codigo")
    assert ba.loc["06218+06466", ["pob_2001", "pob_2010"]].notna().all()
    assert ba.loc["06218", ["pob_2001", "pob_2010"]].isna().all()
    assert pd.isna(ba.loc["06466", "pob_2001"]) and ba.loc["06466", "pob_2022"] > 0
    tdf = cargar_censo("departamentos:94").set_index("codigo")
    assert "94008+94011" in tdf.index
    assert "94028" not in tdf.index  # Antártida e Islas: fuera del mapa


def test_zonas_salta_cubren_los_23_departamentos_y_suman_el_total():
    tabla = zonas("salta")
    assert set(tabla["codigo"]) == set(config.DEPARTAMENTOS_SALTA)
    assert tabla.set_index("codigo").loc["66091", "zona"] == "Puna"  # La Poma
    z = cargar_censo("zonas:salta")
    d = cargar_censo("salta")
    assert censos_disponibles(z) == censos_disponibles(d)
    for anio in censos_disponibles(d):
        assert z[f"pob_{anio}"].sum() == d[f"pob_{anio}"].sum()


def test_zonas_argentina_suman_las_provincias():
    z = cargar_censo("zonas:argentina")
    p = cargar_censo("provincias")
    assert set(zonas("argentina")["codigo"]) == set(config.PROVINCIAS)
    assert censos_disponibles(z) == censos_disponibles(p)
    for anio in censos_disponibles(p):
        col = columna(p, anio)
        assert float(z[col].sum()) == pytest.approx(float(p[col].sum()))
