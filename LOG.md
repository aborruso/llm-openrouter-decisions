# Log

## 2026-10-25

- Project created from the `simonw/llm-plugin` cookiecutter template; code derived from `llm-typesafe` (Apache-2.0).
- Registers every model of the OpenRouter decisions catalog (`/api/v1/models?output_modalities=decisions`, 30 models), cached for an hour.
- Answer types: noul, choice, score, box. Image attachments on models that read images (PNG/JPEG only for Jev). `-o questions` for several questions per request. `-o input_format json`.
- 82 tests pass. Live checks on Jev 1.14 (text, images, box, multiple questions), Microsoft Decision-1 (text), remote image URL.
- `:free` models return HTTP 404 when the OpenRouter privacy settings exclude training on user data.
- README examples: `examples/city_reports.csv` made with fauxdata, `examples/chart.png` and `chart-box.png` from Eurostat URB_CPOP1 data.
