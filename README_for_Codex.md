# Icon Pack Extension Tool

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

## Iteration Loop

1. Open `preview.html`
2. For weak icons, put manual replacement SVG into:
   - `output/<session>/curated_svgs/<slug>.svg`
3. Rebuild preview only:

```bash
python -m app.main preview --config ./config.json --reference ./assets/base_pack/reference_grid.png --output ./output/<session>
```

## Full Pipeline Internals

The pipeline still contains modular stages:
- generation (single icon mode)
- pre-vector cleanup (threshold + component selection + normalization)
- SVG vectorization
- quality scoring (`good`, `needs_cleanup`, `bad_trace`)
- inline-SVG HTML preview
- ZIP packaging

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

Current generator is `MockImageGenerator` for deterministic local demo.
Replace it with a real model backend by implementing `ImageGenerator` in `app/generation.py`.
