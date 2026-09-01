# perler-svg-pattern

Codex Skill for converting existing image files directly into professional SVG Perler Beads patterns.

## Design Principle

This Skill is **stateless**.

It does not store user input images and it does not keep generated SVG files inside the Skill installation directory.

Codex passes the existing source image path directly to the Skill and selects the output path in the current workspace.

## Structure

```text
perler-svg-pattern/
├── SKILL.md
├── pyproject.toml
├── .gitignore
├── README.md
├── scripts/
│   ├── __init__.py
│   ├── image_to_pattern.py
│   ├── palette.py
│   ├── cleanup.py
│   ├── svg_renderer.py
│   └── validate_pattern.py
├── assets/
│   └── palettes/
│       └── README.md
└── tests/
    └── __init__.py
```

There is intentionally no `input/` or `output/` directory in the Skill package.

## Python Environment

Python is restricted to 3.13.x:

```text
>=3.13,<3.14
```

Recommended:

```bash
uv python install 3.13
uv sync
```

## Codex Invocation

Codex should call the Skill using the source image's existing path:

```bash
uv run python <SKILL_DIR>/scripts/image_to_pattern.py   --input "/path/to/current/image.png"   --output "/path/to/current/workspace/pattern.svg"
```

If `--output` is omitted, the generated SVG defaults to the **current working directory**, never the Skill directory.

Example:

```bash
cd /Users/me/my-project

uv run python ~/.codex/skills/perler-svg-pattern/scripts/image_to_pattern.py   --input ./portrait.png
```

Expected destination:

```text
/Users/me/my-project/portrait_perler_56x56.svg
```

## Available Conversion Controls

The converter now performs subject-aware cropping, high-quality downscaling,
adaptive quantization, isolated-cell cleanup, SVG rendering, and final SVG
validation in one command.

```bash
uv run python scripts/image_to_pattern.py \
  --input ./portrait.png \
  --output ./portrait-pattern.svg \
  --max-colors 16 \
  --auto-size
```

- `--auto-size`: adjusts the grid to the estimated subject aspect ratio (24–112 cells per side), while retaining the requested width/height as a baseline.
- `--no-crop`: preserves the full image with white padding instead of using subject-aware cropping.
- `--palette`: loads a verified JSON or CSV physical bead palette; otherwise generic `C01`… IDs are generated.
- `--cell-size`: adjusts SVG bead spacing for screen or print use.

The SVG contains one vector circle per bead, numbered row/column axes, a white
printable background, and a legend with each ID, HEX value, and bead count.

## Buildability and Print Controls

```bash
uv run python scripts/image_to_pattern.py \
  --input ./portrait.png \
  --output ./portrait-plan.svg \
  --min-component-size 3 \
  --bead-shape square \
  --bead-diameter-mm 4.8 \
  --bead-pitch-mm 5 \
  --preview \
  --a4-pages
```

- `--min-component-size`: merges smaller same-colour islands into adjacent colours. The default is three beads.
- `--bead-shape`, `--bead-diameter-mm`, and `--bead-pitch-mm`: control the vector construction geometry. The final grid size is `grid cells × pitch`; `--finished-width-mm` derives pitch from a requested finished width.
- `--bead-size-mm`: convenience shorthand that sets both diameter and pitch, for example `--bead-size-mm 5`.
- `--crop x,y,width,height`, `--mirror`, and `--rotate`: make source framing and orientation deliberate before conversion.
- `--remove-background --background-color '#F8FAFC'`: estimates foreground and replaces the surrounding background with a single colour.
- `--preview`: writes a clean `<name>_preview.svg` in addition to the coordinate construction plan.
- `--a4-pages`: writes full-scale, numbered A4 tile SVGs into `<name>_a4_pages/`; every tile includes global row/column coordinates and dashed tile boundaries. Print these at 100% scale.

## Physical Brand Palettes and Shopping Lists

Use one of the source-documented built-in palettes with `--brand`:

```bash
uv run python scripts/image_to_pattern.py \
  --input ./portrait.png \
  --output ./portrait-hama.svg \
  --brand hama-midi-official \
  --color-distance lab \
  --inventory '01:1000,18:500,28:250' \
  --inventory-bias 0.12
```

- Built-ins: `perler-midi-open-stock-2025`, `hama-midi-official`, and `artkal-s-midi-official`. Their files retain the official source URL and retrieval date.
- `--color-distance lab` uses CIE Lab / Delta E (CIE76); `rgb` uses RGB Euclidean distance. Lab is the default and usually handles close skin and shadow colours more naturally.
- `--inventory` accepts `ID[:quantity],...` or a JSON/CSV inventory file. It favors owned colours only when they are sufficiently close; `--inventory-only` restricts matching to owned IDs.
- A `<name>_shopping.csv` is always produced. It lists brand/series, ID, name, HEX reference, required bead count, quantity on hand, and quantity to buy. Omitted IDs are treated as zero stock; IDs supplied without a quantity keep the purchase amount blank for manual confirmation. Use `--shopping-list path.json` for JSON.

## Image-Type Strategies

Choose an intentional image strategy with `--mode`:

- `portrait`: uses local face detection when possible, expands the crop to retain hair and clothing, and protects fine facial/eye edges while retaining more skin-tone detail.
- `pet`: favors the detected animal silhouette, eye/high-contrast edge details, and distinct fur regions.
- `logo`: retains the full frame, uses nearest-neighbour resampling, and disables cleanup so crisp logo and pixel-art cells are not merged away.
- `landscape`: limits the palette to 14 colours, applies stronger region cleanup, and focuses on the main salient area to reduce background complexity.
- `illustration` / `art`: preserves strong line-art edges with gentler cleanup for hand-drawn and anime-style artwork.
- `auto`: balanced default behaviour.

For example:

```bash
uv run python scripts/image_to_pattern.py \
  --input ./portrait.png \
  --output ./portrait-pattern.svg \
  --mode portrait
```

`--min-component-size` and `--cleanup-passes` remain available when you need to override a mode's cleanup policy.

## Quality Gates and Repeatable Acceptance

Every generated construction-plan SVG is audited before the CLI reports success:

- exact vector bead-cell count, full row/column coverage, and no duplicate cells;
- cell colour IDs and HEX fills match the pattern palette and per-colour totals;
- one legend row per palette colour, with matching count;
- palette ceiling is respected; and
- no embedded raster image, gradient, pattern, filter, mask, or transparency.

Run the complete validation suite with:

```bash
uv run --group dev python -m pytest -q
```

[`tests/fixtures/`](/Volumes/柯影数智/研发部/skill/perler-svg-pattern/tests/fixtures) provides inspectable horizontal, vertical, low-colour, and no-subject inputs. The transparent-PNG case is generated during testing. `regression_baselines.json` stores reviewed grid hashes and expected palettes; a baseline changes only after a deliberate visual review.

## CLI Outputs and Processing Report

The CLI always emits a construction SVG, a shopping list, and a JSON report. Use
`--preview` to add a clean preview SVG and `--a4-pages` for print tiles.

```bash
uv run python scripts/image_to_pattern.py \
  --input ./source.png \
  --output ./pattern.svg \
  --mode art \
  --bead-size-mm 5 \
  --preview \
  --shopping-list ./shopping.json \
  --report ./report.json
```

The report records original and transformed image size, explicit and detected
crop regions, grid/physical dimensions, palette and per-colour counts, cleanup
configuration, cells changed by cleanup, bead totals before/after cleanup, and
every generated artifact path. Its `pattern.grid` and `pattern.palette` also
make it a complete JSON construction manifest.

Common failure messages point to the next action: one-pixel source images are
rejected as non-buildable, malformed palettes explain the required JSON/CSV
schema, and unwritable output destinations ask for a writable target path.

## Artifact Rules

- Never copy user images into the Skill.
- Never write generated SVG files into the Skill.
- Never create `<SKILL_DIR>/input`.
- Never create `<SKILL_DIR>/output`.
- Intermediate files should use memory or a system/Codex temporary directory.
- User artifacts belong to the current Codex workspace or an explicitly requested path.
