# Estrategia de pruebas

Cada caso lleva el ID de la técnica que lo diseñó en el nombre o en el id del parámetro
(`EP-22`, `BVA-06`, `DT-03`, `ST-I4`, `EG-20`, `CL-05`, `AC-05`, `BR-08`). El reporte con el análisis de
riesgo, la derivación de cada técnica y la trazabilidad de los 193 casos se genera en
`reportes-pruebas/` (HTML + PDF).

La suite sigue el Testing Trophy de Kent C. Dodds: estático en la base, unit, integración y E2E arriba.
La prioridad al escribirla fue integración, luego E2E, luego unit. Integración es la capa con más casos (116) y sola cubre 84 % de las ramas contra 35 % de unit: es la
capa que más confianza da, la copa del trofeo.

| Capa | Dónde | Casos | Tiempo | Cobertura de ramas sola |
|---|---|---|---|---|
| Estático | Ruff, `[tool.ruff]` en `pyproject.toml` | 0 hallazgos | <1 s | no aplica |
| Unit | `tests/unit/` | 71 | 0,4 s | 35 % |
| Integración | `tests/integration/` | 116 | 6 s | 84 % |
| E2E | `tests/e2e/` | 6 | 3 s + 70 s del render | subproceso, no se mide |

```bash
uv run ruff check .                      # estático
uv run pytest                            # unit + integración + e2e, sin el render lento
uv run pytest -m integration             # una capa
uv run pytest -m "" --cov=worshipdeck --cov-branch   # todo, con el render de LibreOffice
```

CI (`.github/workflows/ci.yml`) corre las capas en orden y cada una es gate de la siguiente:
`static` → `test` (unit + integración) → `e2e` (con LibreOffice).

## Estático

Ruff agrupa sus reglas en las tres cubetas de la skill: bug (`F`, `E9`, `B`, `PLE`), error (`PLW`, `RUF`)
y style (`I`, `E4`, `E7`, `SIM`). Con `--select ALL` el código daba 950 hallazgos; con estas cubetas
dio 30, todos corregidos. Entre ellos había 2 `zip` sin `strict`, una variable muerta en `parse_hymn`
y 3 `subprocess.run` sin `check` explícito.

## Qué técnica diseñó cada prueba

| Técnica | Prueba | Qué fija |
|---|---|---|
| Particiones de equivalencia | `integration/test_flyer_to_spec.py::test_line_partition` | himno por número, canción de la biblioteca, himno por título, pasaje, ruido, decoración |
| Valores frontera | mismo archivo; `integration/test_hymnal_contract.py::test_hymn_number_boundaries` | himnos 0/1/412/413, corte difuso 0,8 ("Al estar" no basta) |
| Valores frontera | `unit/test_techniques.py` | 27/28/29 caracteres para 4 líneas por slide, confianza 59/60/61, sábado/domingo/lunes/cambio de año |
| Tabla de decisión | `unit/test_techniques.py::test_doubtful_line_decision_table` | 8 reglas: confianza baja × hay match × se puede preguntar |
| Transición de estados | `unit/test_techniques.py::test_ask_loop_transitions` | Dudosa → Resuelta / Dudosa otra vez / Descartada / Pendiente |
| Contrato de datos | `integration/test_hymnal_contract.py` | `hymnal.json` contra el builder y contra el parser del PDF |
| Caracterización | `integration/test_build_real_template.py::test_hymn_64_matches_the_operators_deck` | el Himno 64 sale igual que en la deck que la operadora entregó el 6 de septiembre |
| Error guessing | `integration/test_ocr_and_cli.py` | número mal leído y línea que tesseract se salta entera: ambos llegan como pregunta con recorte |
| E2E por journey | `e2e/test_cli_e2e.py` | flyer → deck de 72 slides, PDF de letras, preguntas en una pseudo-terminal real, imagen inexistente |

## Defectos que encontró la suite

- `CHORUS_RE` del parser del PDF tomaba "Coronadle…" (Himno 225) como marcador de coro.
  Lo encontró `test_json_and_pdf_parser_agree`, y lo corrige el `\b` en `builder.py:46`.
- Una respuesta "Hosana!!" sí coincide con "Hosanna" por el match difuso. El test estaba mal,
  el código bien: el caso quedó documentado en `test_ask_loop_transitions`.

## Mutantes

Cobertura dice qué corrió, no qué se verificó. Planté mutantes a mano y la suite los mató todos (el reporte
lista 8, con 2 sobre la frontera de confianza de la API):

| Mutante | Lo mata |
|---|---|
| `conf < MIN_CONF` → `<=` | `test_confidence_boundary_decides_who_gets_asked[60]` |
| corte difuso 0,8 → 0,6 | `test_line_partition[Al estar]` |
| segundo coro ignorado | `test_second_chorus_closes_hymn_44` |
| `<= 28` → `< 28` | `test_auto_chunk_size_boundary[28]` |
| bandas sin leer nunca reportadas | `test_interactive_questions_through_a_real_terminal` |
| matches con baja confianza fuera de pendientes | `test_without_ask_shaky_matches_are_kept_and_listed` |
