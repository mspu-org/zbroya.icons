# zbroya.icons

Desktop app for iterative icon-pack extension.

## Run Desktop UI

```bash
python -m app.main desktop --config ./config.json --output-root ./output
```

## What is now implemented

- OpenAI-ready generation flow in GUI (provider/model/API key controls)
- Iteration sessions list and run log
- Quality tables with dedicated `Needs cleanup` tab
- Intermediate debug stage viewer (`gray`, `mask_raw`, `mask_clean`, `crop`, `norm`)
- Side-by-side preview: source PNG vs SVG-render preview
- Manual curation in GUI:
  - drag-and-drop SVG override (when `tkinterdnd2` available)
  - file-picker override fallback
  - one-click `Rebuild Preview` without full rerun
- Auto-retry for `bad_trace` in curated mode using stricter cleanup/vectorization settings

## OpenAI setup

1. Put API key in GUI field `OpenAI API key` (or env var `OPENAI_API_KEY`).
2. In GUI select provider `openai` and model (default `gpt-image-1`).
3. Run iteration.

## CLI One-Click (still available)

```bash
python -m app.main one-click --reference ./assets/base_pack/reference_grid.png --entities "Defense Equipment Manufacturer; Defence Tech Startup; Dual-Use Technology"
```

## Build Windows EXE

```powershell
.\build-exe.ps1
```

Output:
- `dist\IconPackStudio.exe`

## Manual override path

For selected session + slug, curated SVG is stored as:
- `output/<session>/curated_svgs/<slug>.svg`

## Requirements

- Python 3.11+
- `pip install -r requirements.txt`

## Note

OpenAI provider currently enforces style through prompting constraints; reference image is used as style context in pipeline metadata but not directly uploaded in this endpoint path.
