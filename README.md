# zbroya.icons

One-command pipeline for extending an icon pack from a reference style set.

## Desktop UI (Recommended)

Run from source:

```bash
python -m app.main desktop --config ./config.json --output-root ./output
```

In UI you can:
- set reference image and entities
- run new iterations
- review per-icon quality status
- inspect debug intermediates (`gray`, `mask_raw`, `mask_clean`, `crop`, `norm`)
- open preview HTML, output folder, ZIP

## Build Windows EXE

Build command:

```powershell
.\build-exe.ps1
```

Output executable:
- `dist\IconPackStudio.exe`

No console window, full GUI app.

## CLI One-Click

```bash
python -m app.main one-click --reference ./assets/base_pack/reference_grid.png --entities "Defense Equipment Manufacturer; Defence Tech Startup; Dual-Use Technology"
```

Or PowerShell wrapper:

```powershell
.\Start-IconPreview.ps1 -Reference .\assets\base_pack\reference_grid.png -EntitiesFile .\assets\examples\new_icons.txt
```

## Generation Providers

Configure in `config.json`:
- `generation.provider = "mock"` for local deterministic demo
- `generation.provider = "openai"` for real image generation

For OpenAI provider, set API key env var before run:

```powershell
$env:OPENAI_API_KEY = "<your_api_key>"
```

Then set in `config.json`:

```json
"generation": {
  "provider": "openai",
  "openai_model": "gpt-image-1",
  "openai_base_url": "https://api.openai.com/v1",
  "openai_api_key_env": "OPENAI_API_KEY"
}
```

## Iteration Loop

1. Generate a new iteration (Desktop UI or CLI).
2. Open `output/<session>/preview.html`.
3. If needed, put manual SVG override to `output/<session>/curated_svgs/<slug>.svg`.
4. Rebuild preview only:

```bash
python -m app.main preview --config ./config.json --reference ./assets/base_pack/reference_grid.png --output ./output/<session>
```

## Requirements

- Python 3.11+
- `pip install -r requirements.txt`

## Note

OpenAI provider currently applies style via prompting constraints; it does not upload reference images directly in this endpoint path.
