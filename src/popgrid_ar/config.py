"""Rutas, fuentes y catálogos fijos del proyecto."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data"
CRUDOS = DATOS / "raw"
LIMITES = DATOS / "limites"
CENSOS = DATOS / "censos"
ZONAS = DATOS / "zonas"  # agrupaciones de departamentos: <provincia>.csv (codigo,departamento,zona)
SALIDA = RAIZ / "output"

# Servicio WFS del Instituto Geográfico Nacional. La capa `ign:departamento`
# trae el código INDEC de 5 dígitos en `in1` (2 de provincia + 3 de departamento).
IGN_WFS = "https://wms.ign.gob.ar/geoserver/ows"
IGN_CAPA_DEPARTAMENTOS = "ign:departamento"

# CRS métrico para simplificar geometrías (POSGAR 2007 / Argentina 4).
CRS_METRICO = "EPSG:5346"
TOLERANCIA_SIMPLIFICACION_M = 250

# Departamentos que se excluyen de los mapas: no tienen población censada
# comparable y su superficie deformaría el mapa de Tierra del Fuego.
DEPARTAMENTOS_EXCLUIDOS = {
    "94021": "Islas del Atlántico Sur",
    "94028": "Antártida Argentina",
}

# Departamentos creados después de 2010: en los censos indicados, su población
# está contada dentro del departamento de origen. nuevo -> (origen, censos).
CONTENIDOS = {
    "06466": ("06218", (2001, 2010)),  # Lezama, dentro de Chascomús
    "94011": ("94008", (2001, 2010)),  # Tolhuin, dentro de Río Grande
}

# Códigos INDEC de provincia -> nombre corto para los mapas.
PROVINCIAS = {
    "02": "CABA",
    "06": "Buenos Aires",
    "10": "Catamarca",
    "14": "Córdoba",
    "18": "Corrientes",
    "22": "Chaco",
    "26": "Chubut",
    "30": "Entre Ríos",
    "34": "Formosa",
    "38": "Jujuy",
    "42": "La Pampa",
    "46": "La Rioja",
    "50": "Mendoza",
    "54": "Misiones",
    "58": "Neuquén",
    "62": "Río Negro",
    "66": "Salta",
    "70": "San Juan",
    "74": "San Luis",
    "78": "Santa Cruz",
    "82": "Santa Fe",
    "86": "Santiago del Estero",
    "90": "Tucumán",
    "94": "Tierra del Fuego",
}

CODIGO_SALTA = "66"

# Códigos INDEC de los 23 departamentos de Salta (según IGN).
DEPARTAMENTOS_SALTA = {
    "66007": "Anta",
    "66014": "Cachi",
    "66021": "Cafayate",
    "66028": "Capital",
    "66035": "Cerrillos",
    "66042": "Chicoana",
    "66049": "General Güemes",
    "66056": "General José de San Martín",
    "66063": "Guachipas",
    "66070": "Iruya",
    "66077": "La Caldera",
    "66084": "La Candelaria",
    "66091": "La Poma",
    "66098": "La Viña",
    "66105": "Los Andes",
    "66112": "Metán",
    "66119": "Molinos",
    "66126": "Orán",
    "66133": "Rivadavia",
    "66140": "Rosario de la Frontera",
    "66147": "Rosario de Lerma",
    "66154": "San Carlos",
    "66161": "Santa Victoria",
}

# Serie histórica de Salta (1869-2022). Departamentos que en algunos censos no
# formaban parte de la provincia: no se dibujan en esos años.
AUSENCIAS_SALTA = {
    "66105": (1869, 1895),  # Los Andes: ex gobernación de Los Andes, anexada en 1943
}
# Filas compuestas (códigos unidos con "+") para departamentos que luego se dividieron.
SEPARADOR_COMPUESTO = "+"

# INDEC, Censo 2010, Tomo 1, Cuadro 7: % de la población del país sin provincia
# asignada ("jurisdicciones sin determinar"). En los demás censos es 0; si la
# columna no suma 100 es solo por redondeo.
SIN_JURISDICCION_PCT = {1895: 2.2, 1914: 0.2}

# Etiquetas más cortas para nombres que no entran en los bloques.
ETIQUETAS = {
    "Orán y General José de San Martín": "Orán + San Martín",
    "General José de San Martín": "San Martín",
    "Rosario de la Frontera": "R. de la Frontera",
    "Santiago del Estero": "Sgo. del Estero",
}

# Ejemplos de niveles (ver popgrid_ar.niveles para la sintaxis completa).
NIVELES = ("provincias", "salta", "zonas:salta")
