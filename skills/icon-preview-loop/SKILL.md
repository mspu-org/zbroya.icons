---
name: icon-preview-loop
description: Run a one-command icon-pack extension loop from a reference PNG/SVG and a free-form entities prompt, then produce preview.html for iterative curation. Use when user wants the pipeline hidden and asks to provide base icon set + entity list and immediately review results in HTML.
---

Execute this flow:

1. Collect `reference` path and free-form entities text (bullets, lines, or comma-separated).
2. Run one command from project root:

```powershell
python -m app.main one-click --reference <REFERENCE_PATH> --entities "<ENTITIES_TEXT>"
```

If text is long, save it to a file and run:

```powershell
python -m app.main one-click --reference <REFERENCE_PATH> --entities-file <ENTITIES_FILE>
```

3. Return path to generated preview page and manifest:
- `output/<session>/preview.html`
- `output/<session>/manifest.json`
- `output/<session>/icon_pack_bundle.zip`

4. For iteration, apply manual SVG overrides:
- put curated SVG into `output/<session>/curated_svgs/<slug>.svg`
- rebuild preview only:

```powershell
python -m app.main preview --config config.json --reference <REFERENCE_PATH> --output output/<session>
```

5. Keep iteration tight:
- prioritize icons marked `needs_cleanup` or `bad_trace`
- rerun only needed step (`preview` after override, `one-click --force` for full regen)

Use `Start-IconPreview.ps1` when user asks for a button-like entry point.
