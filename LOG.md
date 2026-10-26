# Log

## 2026-10-26

- New command `llm openrouter-decisions batch`: one question on every row of CSV/TSV/JSON/JSONL, concurrent requests (default 8, max 32), `--limit`, `--max-cost`, `--resume`, `--log`, retry on 429/5xx, stop on 401/402. 16 new tests (98 total). Live on 100 titles: 4.0 s, $0.00125, max 0.04 from the script results. README section "Large batches" with costs, limits and risks.
- Concurrency spike, 100 titles, Jev 1.14: 4.1 s (8), 2.6 s (16), 2.5 s (32), no 429.
- README, "Large batches from Python": new reproducible example. 500 OpenAlex titles with "transparency" (2024, fixed seed) in `examples/publications.csv`, download script `examples/fetch_publications.sh`, `examples/batch.py`, results in `examples/publications_scored.csv`. Measured: 18.2 s, $0.0063; probabilities vary up to 0.06 between runs. The old 145-title file was never committed.

## 2026-10-25

- README: link to vd-jev, the VisiData plugin for the same Decisions API.
- LinkedIn carousel in `carousel/`: 8 Typst cards, 4:5, PDF for the document post, plus the post text.
- Commented on simonw/llm-typesafe#1 (OpenRouter support); opened simonw/llm#1821 to add the plugin to the LLM plugin directory.
- Release 0.1a0, first alpha: published on GitHub as a pre-release and on PyPI.
- Project created from the `simonw/llm-plugin` cookiecutter template; code derived from `llm-typesafe` (Apache-2.0).
- Registers every model of the OpenRouter decisions catalog (`/api/v1/models?output_modalities=decisions`, 30 models), cached for an hour.
- Answer types: noul, choice, score, box. Image attachments on models that read images (PNG/JPEG only for Jev). `-o questions` for several questions per request. `-o input_format json`.
- 82 tests pass. Live checks on Jev 1.14 (text, images, box, multiple questions), Microsoft Decision-1 (text), remote image URL.
- `:free` models return HTTP 404 when the OpenRouter privacy settings exclude training on user data.
- Removed the PyPI publish workflow: releases are uploaded by hand with twine, following `docs/release.md` (local `/release` skill).
- ruff fixes (unused import, import order, f-string).
- README examples: `examples/city_reports.csv` made with fauxdata, `examples/chart.png` and `chart-box.png` from Eurostat URB_CPOP1 data.
