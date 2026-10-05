# CLAUDE.md — worshipdeck

Genera la presentación del culto dominical de Iglesia Evangélica Amigos (PPTX) desde la foto del
flyer. Port a programa de la skill `ppt` (`danihrndzld/worship-deck-builder`): el builder es el mismo,
lo nuevo es OCR → spec, la Biblia RVR1960, la API web y la app. Repo público:
`danihrndzld/worshipdeck`; producción: https://worshipdeck-seven.vercel.app

## Comandos

```bash
uv sync
uv run ruff check .                                   # estático (cubetas bug/error/style en pyproject)
uv run pytest                                         # 195 casos, ~7 s, sin el render de LibreOffice
uv run pytest -m ""                                   # todo, incluido el render (+70 s)
uv run worshipdeck make flyer.jpg --sermon-title X --passage "Salmos 23:1-6"
uv run worshipdeck parse flyer.jpg -o spec.json       # pregunta en la terminal por líneas dudosas
uv run flask --app worshipdeck.web run --port 5077    # app web local
```

Requiere `tesseract` con `spa.traineddata` (`/opt/homebrew/share/tessdata/`) para el CLI y los tests
de integración/E2E; `soffice` solo para el test marcado `slow`.

## Mapa

| Ruta | Qué |
|---|---|
| `worshipdeck/flyer.py` | OCR (tesseract TSV), bandas de tinta sin leer, clasificación de líneas, ciclo de preguntas, spec |
| `worshipdeck/bible.py` | cita → versículos y slides (6 líneas por slide) desde `data/rvr1960.json` |
| `worshipdeck/builder.py` | builder de la skill: clona slides de `reference/style-template.pptx` |
| `worshipdeck/web.py` | API Flask + sirve `web/`; entrypoint de Vercel en `[tool.vercel]` de `pyproject.toml` |
| `worshipdeck/cli.py`, `lyrics_pdf.py` | CLI (`make`, `parse`, y los subcomandos de la skill); PDF de letras |
| `web/` | SPA en JS plano, sin build (13 pantallas del mockup de Claude Design); OCR con tesseract.js |
| `data/hymnal.json` | 412 himnos de Corazón y Vida (`tools/extract_hymnal.py`); 22 con `needs_review` |
| `data/rvr1960.json` | 31 104 versículos (`tools/extract_bible.py`, fuente mrk214/bible-data-es-spa) |
| `reference/song-library/` | canciones contemporáneas aprobadas, una por JSON; se agregan con `song import-deck` / `song add` |
| `reference/decks/` | decks reales (AGOSTO 30, SEPTIEMBRE 6) usadas como oráculo en los tests |
| `tests/{unit,integration,e2e}/` | Testing Trophy; estrategia en `tests/README.md` |
| `reportes-pruebas/` | reporte PDF de la skill `testing-and-continuous-delivery` |

## Reglas del dominio (de la skill `ppt`, no negociables)

- Nunca editar la letra del himnario; solo se corrige pegado de OCR. El título va completo, en oración.
- Pasajes siempre en Reina-Valera 1960, textuales.
- Las canciones contemporáneas salen solo de `reference/song-library/`, nunca de sitios de letras.
  En Vercel la biblioteca es de solo lectura: agregar una canción es PR + merge + tag.
- El PDF de letras sale solo de una deck que la operadora ya revisó (`--reviewed` / `reviewed=true`).
- Una deck editada a mano no se reconstruye: se usa `insert`.

## Pruebas

- Cada test lleva el ID de la técnica que lo diseñó en el nombre o en el id del parámetro:
  `EP`, `BVA`, `DT`, `ST`/`ST-I`, `EG`, `CL`, `AC`, `BR`. Un test nuevo sigue la numeración correlativa.
- Un test que expone un defecto se queda fallando hasta corregir el código; no se ajusta el esperado.
- BVA-36 falla si una deck pasa 4,5 MB (límite de respuesta de Vercel).

## CI y release

- `ci.yml`: build, lint, unit, integration y e2e en paralelo; `coverage` exige ≥ 80 % de ramas; `gate`
  es el check único (fan-in). `build.yml` lo comparten CI y release.
- Release = tag `v*` (subir antes `version` en `pyproject.toml`): build → GitHub release → deploy a
  Vercel con el secret `VERCEL_TOKEN`. Actions fijadas por SHA, `vercel` CLI por versión.

## Trampas conocidas

- Vercel corta respuestas en 4,5 MB: si cambia la plantilla, correr `tools/compress_template.py`.
- No volver a poner un rewrite catch-all en `vercel.json`: Vercel le pasa a Flask la ruta reescrita y
  todo da 404 (pasó en v0.1.0).
- `gh secret set` con el prefijo `!` guarda un valor vacío; cargar secrets desde GitHub o una terminal
  propia.
- Al verificar la app en Chrome, cambiar solo el hash de la URL no recarga `app.js`: recargar la página.
- Chrome bloquea el puerto 5061 (`ERR_UNSAFE_PORT`); usar 5077.
- El wheel no incluye `data/` ni `reference/`: el CLI corre desde el checkout del repo.

## Git

Autor: `Daniel Hernández <danisnowman@gmail.com>`, sin atribución a Claude (regla global).
