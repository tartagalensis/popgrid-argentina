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

---

# Salta 1869-2022: `salta_historico.csv`

Lo genera [`scripts/construir_salta_historico.py`](../../scripts/construir_salta_historico.py).

| Censos | Cuadro | Archivo |
|---|---|---|
| 1869, 1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010 y 2022 | Dirección General de Estadísticas de Salta, Anuario 2025, cuadro 2.1.1: *"Población según departamento. Provincia de Salta. Años 1869, 1895, 1914, 1947, 1960, 1970, 1980, 1991, 2001, 2010 y 2022"*. Fuente primaria declarada en el cuadro: INDEC, censos nacionales. | `https://estadisticas.salta.gov.ar/web/archivos/anuarios/ANUARIO-2025/02-POBLACIÓN Y HOGARES/2.01 Población/A25-2-1-1.xlsx` (página: [2.01 Población](https://estadisticas.salta.gov.ar/web/level3/2/2/1395/1/null)) |

Fecha de consulta: 13/11/2026.

## Controles

- En los 11 censos, los departamentos suman exactamente el total provincial del cuadro.
- 2001, 2010 y 2022 coinciden, departamento por departamento, con los cuadros del INDEC
  de `departamentos.csv`.

## Totales de Salta

| 1869 | 1895 | 1914 | 1947 | 1960 | 1970 | 1980 | 1991 | 2001 | 2010 | 2022 |
|---|---|---|---|---|---|---|---|---|---|---|
| 88.933 | 118.015 | 142.156 | 290.826 | 412.854 | 509.803 | 662.870 | 866.153 | 1.079.051 | 1.214.441 | 1.441.351 |

Ojo: algunas fuentes secundarias (por ejemplo, Wikipedia) dan 230.445 para 1947.
Esa cifra deja afuera a Orán y San Martín (60.381 personas), que en el cuadro
aparecen en una fila sin nombre.

## Cambios de límites (notas del cuadro)

| Caso | Qué dice el cuadro | Cómo se trata |
|---|---|---|
| Orán y General José de San Martín | Hasta 1947 eran un solo departamento, Orán (nota 4). | Fila compuesta `66126+66056`, con valores de 1869 a 1947. En esos años las filas de Orán y San Martín quedan vacías. En los mapas se dibuja la unión de los dos. |
| Los Andes | Sin dato en 1869 y 1895. En 1914 figura la población de los departamentos San Antonio de los Cobres y Pastos Grandes, de la ex gobernación de Los Andes, que se anexaron a Salta en 1943 (nota 3). El total de 1914 la incluye. | Vacío en 1869 y 1895 (`config.AUSENCIAS_SALTA`): no se dibuja esos años. En 1914 se usa el valor del cuadro. |
| La Poma, 1914 | Excluye el pueblo de San Antonio de los Cobres, que había pasado a la gobernación de Los Andes (nota 2). | Se usa el valor del cuadro. |
| General Güemes | Hasta 1947 se llamaba Campo Santo (nota 1). | Mismo código y mismo territorio; solo cambia el nombre. |

Los mapas usan los límites actuales del IGN para todos los años. Otros cambios
menores de límites entre departamentos no están documentados en el cuadro y no
se corrigen.

---

# Provincias 1895-1991: `provincias_historico.csv`

Lo genera [`scripts/construir_provincias_historico.py`](../../scripts/construir_provincias_historico.py).

| Censos | Cuadro | Archivo |
|---|---|---|
| 1895, 1914, 1947, 1960, 1970, 1980 y 1991 | INDEC, Censo 2010, Resultados definitivos, Serie B nº 2, Tomo 1, Cuadro 7: *"Distribución relativa de la población según provincia. Total del país. Años 1895/2010"* (pág. 63 de la publicación, 64 del PDF). | [`censo2010_tomo1.pdf`](https://www.indec.gob.ar/ftp/cuadros/poblacion/censo2010_tomo1.pdf) |

**El dato es un porcentaje con un decimal, no una cantidad de personas.** Es lo
único que el INDEC publica por provincia para esos censos en una sola serie
oficial. Por eso las columnas se llaman `pct_AAAA`, y no `pob_AAAA`.

## Controles

- Las 24 provincias tienen 9 valores (1895 a 2010).
- Cada censo suma 100 ± 0,6, contando la población sin jurisdicción determinada.
- 2001 y 2010, que también figuran en el cuadro, coinciden con los porcentajes
  calculados desde `provincias.csv`. La diferencia máxima es 0,051 puntos
  (Buenos Aires 2010: 38,949% exacto, publicado como 39,0).

## Notas del cuadro

- **Jurisdicciones sin determinar:** 2,2% en 1895 y 0,2% en 1914. Corresponden a
  60.000 "personas sustraídas a la operación censal" y 30.000 indígenas en 1895, y a
  18.425 personas de "población autóctona" en 1914, sin ubicación geográfica. No se
  reparten entre provincias (`config.SIN_JURISDICCION_PCT`).
- **Valores 0:** Santa Cruz en 1895 (publicado "0,0") y Tierra del Fuego en 1895,
  1914 y 1947 (publicado "–"). Son menos del 0,05% y no llegan a medio bloque, así
  que no se dibujan esos años.
- **Territorios:** antes de su provincialización (1951-1955, y 1990 en Tierra del
  Fuego), Chaco, Formosa, Misiones, La Pampa y la Patagonia eran territorios
  nacionales. El cuadro ya los presenta con los nombres de las provincias actuales.
  La ex gobernación de Los Andes (1900-1943) no aparece aparte en el cuadro.
- **Precisión:** con un decimal, una provincia chica puede tener un error relativo
  grande (0,4 puede ser 0,35 o 0,45). Para comparar entre censos sirve; para calcular
  tasas de crecimiento no conviene.
