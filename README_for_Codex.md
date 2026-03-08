# zbroya.icons

One-command pipeline for extending an icon pack from a reference style set.

## Zero-Complexity Mode (Recommended)

Give:
1. Base icon set PNG/SVG (`--reference`)
2. Free-form entities text (`--entities` or `--entities-file`)

Run:

```bash
python -m app.main one-click --reference ./assets/base_pack/reference_grid.png --entities "Defense Equipment Manufacturer; Defence Tech Startup; Dual-Use Technology"
```

Or use PowerShell wrapper (button-like entry):

```powershell
.\Start-IconPreview.ps1 -Reference .\assets\base_pack\reference_grid.png -EntitiesFile .\assets\examples\new_icons.txt
```

Result:
- `output/<session>/preview.html`
- `output/<session>/manifest.json`
- `output/<session>/icon_pack_bundle.zip`

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

1. Open `preview.html`
2. For weak icons, put manual replacement SVG into:
   - `output/<session>/curated_svgs/<slug>.svg`
3. Rebuild preview only:

```bash
python -m app.main preview --config ./config.json --reference ./assets/base_pack/reference_grid.png --output ./output/<session>
```

## Classic Commands

```bash
python -m app.main full-run --config ./config.json --reference ./assets/base_pack/reference_grid.png --requests ./assets/examples/new_icons.json --output ./output/run_001
python -m app.main generate  --config ./config.json --reference ./assets/base_pack/reference_grid.png --requests ./assets/examples/new_icons.json --output ./output/run_001
python -m app.main vectorize --config ./config.json --requests ./assets/examples/new_icons.json --output ./output/run_001
python -m app.main preview   --config ./config.json --reference ./assets/base_pack/reference_grid.png --output ./output/run_001
python -m app.main package   --config ./config.json --output ./output/run_001
```

## Requirements

- Python 3.11+
- `pip install -r requirements.txt`

## Note

OpenAI provider currently applies style via prompting constraints; it does not upload reference images directly in this endpoint path.
