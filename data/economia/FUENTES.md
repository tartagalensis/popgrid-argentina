# Fuentes de las series económicas

## Exportaciones por provincia de origen, 1993-2025

`exportaciones_provincias.csv` y `exportaciones_otros.csv` los genera
[`scripts/construir_exportaciones.py`](../../scripts/construir_exportaciones.py).

| Dato | Fuente | Archivo |
|---|---|---|
| Exportaciones de bienes por provincia de origen, en millones de USD corrientes | INDEC, Origen provincial de las exportaciones (OPEX), serie por regiones económicas y provincias | [`sh_opex_regiones_economicas_provincias_1993_2025.xls`](https://www.indec.gob.ar/ftp/cuadros/economia/sh_opex_regiones_economicas_provincias_1993_2025.xls) |

Página del INDEC: <https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-2-79>.
Fecha de consulta: 13/11/2026.

- **2024 y 2025 son provisorios** (marcados con * en el cuadro). Los mapas lo aclaran.
- **Sin provincia:** "Extranjero y plataforma continental" e "Indeterminado" no tienen
  provincia. Representan entre 1,5% y 6,2% del total según el año. Quedan en
  `exportaciones_otros.csv`, junto con el Total. Los bloques se reparten entre las
  exportaciones con provincia asignada, y el pie de cada mapa dice qué porcentaje quedó afuera.
- **Control:** en los 33 años, las 24 provincias más esas dos categorías suman el
  Total del cuadro (tolerancia por redondeo: 0,1%).
- Son dólares corrientes. Para comparar la participación de cada provincia entre años
  no importa, pero los montos de años distintos no son comparables entre sí.
- Solo existen por provincia. No hay una serie oficial por departamento.

## PBI: pendiente

Se probó la grilla de PBI de Kummu et al. (2025), la misma fuente que usa popgrid
(Zenodo [10.5281/zenodo.16741980](https://doi.org/10.5281/zenodo.16741980)), sumada
sobre los polígonos del IGN. **Se descartó** por dos problemas:

1. **Quiebre en la serie de Córdoba.** El PBI per cápita de Córdoba en el dataset cae
   de 18.127 (2011) a 11.050 (2022) dólares de 2017, y la provincia queda con el 3,8%
   del PBI del país, cuando tiene el 8,4% de la población. Las estimaciones oficiales
   la ubican bastante más arriba. Es un problema del dataset, no de la suma: popgrid
   trae el mismo 3,8%.
2. **Resolución.** Con celdas de 5' (unos 9 km), parte del PBI de CABA se reparte
   sobre la provincia de Buenos Aires.

La fuente adecuada para las provincias es la **desagregación provincial del valor
agregado bruto** de CEPAL y el Ministerio de Economía (CEP XXI), a precios de 2004:
[CEPAL, publicación 47900](https://www.cepal.org/es/publicaciones/47900-desagregacion-provincial-valor-agregado-bruto-la-argentina-base-2004)
(anexo `Jurisdiccion_52sectores.xlsx`). El sitio de CEPAL bloquea las descargas
automatizadas, así que el archivo hay que bajarlo a mano y dejarlo en
`data/raw/cepal/`.
