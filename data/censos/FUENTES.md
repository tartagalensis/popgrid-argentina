# Fuentes de los datos censales

`provincias.csv` y `departamentos.csv` los genera
[`scripts/construir_censos.py`](../../scripts/construir_censos.py) a partir de los
cuadros oficiales del INDEC. No se editan a mano. Para regenerarlos:

```bash
uv run python scripts/construir_censos.py --forzar
```

Dato: **población total** (incluye a las personas en situación de calle y, en 2022,
también a las que viven en viviendas colectivas). Fecha de consulta: 13/11/2026.

## Cuadros usados (uno de cada tipo por provincia, 48 en total)

| Censos | Cuadro INDEC | Archivo |
|---|---|---|
| 2010 y 2022 | Censo 2022, resultados definitivos (nov. 2023). Cuadro 1.x: *"Total de población, variación absoluta y variación relativa, por departamento. Años 2010 y 2022"*. Trae el código INDEC de cada departamento. | `https://www.indec.gob.ar/ftp/cuadros/poblacion/c2022_<prov>_est_c1_<n>.xlsx` (Salta: [`c2022_salta_est_c1_17.xlsx`](https://www.indec.gob.ar/ftp/cuadros/poblacion/c2022_salta_est_c1_17.xlsx)) |
| 2001 y 2010 | Censo 2010, Cuadro P1-P: *"Población total y variación intercensal absoluta y relativa por departamento. Años 2001-2010"*. Trae solo nombres, sin códigos. | `https://www.indec.gob.ar/ftp/censos/2010/CuadrosDefinitivos/P1-P_<Provincia>.xls` (Salta: [`P1-P_Salta.xls`](https://www.indec.gob.ar/ftp/censos/2010/CuadrosDefinitivos/P1-P_Salta.xls)) |

La lista completa de archivos está en `CUADROS`, dentro del script.
Índices: [Censo 2022](https://www.indec.gob.ar/indec/web/Nivel4-Tema-2-41-165) ·
[Censo 2010](https://www.indec.gob.ar/indec/web/Nivel4-Tema-2-41-135).

## Cómo se unen 2001 y 2022

La población de 2010 aparece en las dos publicaciones. Cada fila 2001-2010 se
empareja con el departamento de 2022 que tiene **la misma población en 2010**
dentro de la provincia. Si hay empate, se desempata por nombre. Así se evitan
errores por nombres escritos distinto en cada publicación.

## Controles que hace el script

- Todas las filas de 2001 tienen par en 2022 y la población de 2010 coincide.
- El total provincial de 2010 es el mismo en las dos publicaciones.
- En cada provincia y en cada censo, los departamentos suman el total provincial.

Los tres controles se cumplen para las 24 jurisdicciones y los 528 departamentos.

## Totales resultantes

| Censo | Total del país | Salta |
|---|---|---|
| 2001 | 36.260.130 | 1.079.051 |
| 2010 | 40.117.096 | 1.214.441 |
| 2022 | 45.892.285 | 1.441.351 |

Coinciden con el Cuadro P1 nacional del Censo 2010
([`P1-P_Total_pais.xls`](https://www.indec.gob.ar/ftp/censos/2010/CuadrosDefinitivos/P1-P_Total_pais.xls)).

## Departamentos con datos faltantes

| Código | Departamento | Qué pasa |
|---|---|---|
| 06466 | Lezama (Buenos Aires) | Partido creado en 2009 a partir de Chascomús. Solo tiene dato de 2022. Su población de 2001 está dentro de Chascomús. |
| 94011 | Tolhuin (Tierra del Fuego) | Departamento nuevo. En 2001 y 2010 su población se contaba dentro de Río Grande. Solo tiene dato de 2022. |

Para comparar esas zonas entre censos hay que sumarlas al departamento de origen
(Chascomús + Lezama, Río Grande + Tolhuin).

## Otras notas

- **Antártida e Islas del Atlántico Sur:** el INDEC publica un solo valor
  (`94028`: 163 en 2001, 207 en 2010 y 81 en 2022). El IGN, en cambio, separa
  `94021` y `94028`. Los mapas excluyen la superficie de los dos.
- **CABA:** el cuadro de 2001 identifica las comunas solo por número. El script
  las nombra "Comuna N" y las une por la población de 2010.
- **Salta:** los 23 departamentos son los mismos, con los mismos nombres, en los tres censos.
- Los cuadros descargados se guardan en `data/raw/indec/`, que git ignora.
