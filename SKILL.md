# Perler SVG Pattern Skill

## Name
perler-svg-pattern

## Purpose
Convert an input image into a professional, physically buildable Perler Beads pattern. The primary artifact is a standalone construction-plan SVG; the Skill also emits a shopping list and a machine-readable JSON processing report.

## Core Requirements

- Automatically detect the main subject.
- Preserve facial expression, silhouette, hairstyle, clothing colors, and signature features.
- Simplify details that cannot be represented reliably with beads.
- Default output grid: 56×56.
- Automatically adjust dimensions when necessary while preserving aspect ratio.
- Maximum palette size: 20 colors by default.
- Remove gradients, shadows, transparency, blur, anti-aliasing, and photographic noise.
- One grid cell must represent exactly one bead.
- Output horizontal and vertical coordinates.
- Output color IDs.
- Output HEX values.
- Output bead count for every color.
- Output total bead count.
- Output must be a standalone SVG.
- White printable background.
- No logos.
- No watermarks.
- SVG must be composed of actual vector grid cells; do not embed the raster source image as the pattern.
- Validate the final SVG for exact grid coverage, legend consistency, colour counts, opaque vector-only rendering, and no embedded bitmap/gradient/filter/mask.
- Default companion artifacts: a CSV shopping list and a JSON processing report.

## Runtime

This skill uses a project-local Python 3.13 environment managed by `uv`.

Preferred execution:

```bash
uv run python scripts/image_to_pattern.py --input <image> --output output/pattern.svg
```

Required Python runtime: `>=3.13,<3.14`.

Do not rely on the system Python environment when the project environment is available.
If Python 3.13 is not installed, prefer `uv python install 3.13` before syncing dependencies.

## Default Workflow

1. Locate the input image.
2. Select an image strategy: `auto`, `portrait`, `pet`, `logo`, `landscape`, or `art` / `illustration`.
3. Load, normalize, and optionally crop/mirror/rotate/remove the background.
4. Detect or estimate the main subject; portrait mode uses local face detection when available.
5. Determine an appropriate bead grid and physical dimensions.
6. Resize while preserving the mode's required edges and composition.
7. Match to a physical palette or quantize to <=20 colours using RGB or Lab / Delta E distance.
8. Apply the mode's connected-region cleanup while protecting signature edges where appropriate.
9. Assign stable colour IDs, count beads, and create the shopping list.
10. Generate the construction-plan SVG, optional clean preview, and optional A4 tile SVGs.
11. Validate SVG geometry, coordinates, colour IDs, fills, counts, legend, palette ceiling, and vector-only constraints.
12. Write the JSON processing report.
13. Return the construction-plan SVG and companion artifact paths.

## Project Components

- `scripts/image_to_pattern.py`
  Main CLI and orchestration entry point.
- `scripts/palette.py`
  Palette loading, color conversion, and nearest-color matching.
- `scripts/cleanup.py`
  Low-frequency color merging and isolated-cell cleanup.
- `scripts/svg_renderer.py`
  SVG construction plan, preview, physical dimensions, and A4-tile rendering.
- `scripts/validate_pattern.py`
  Grid, palette, SVG geometry, legend, and vector-only artifact validation.
- `scripts/report.py`
  JSON conversion-report writer.

## Palette Rules

Use `--brand` to select a shipped, source-documented physical palette when the user specifies a compatible brand:

```text
perler-midi-open-stock-2025
hama-midi-official
artkal-s-midi-official
```

Use an explicitly supplied verified JSON/CSV palette with `--palette` when applicable.

Never invent commercial bead color codes.

Use `--color-distance lab` by default for physical-palette matching; `rgb` is available when specifically desired. `--inventory` can prioritize owned colour IDs, and `--inventory-only` restricts matching to them.

If no verified palette exists, use generic IDs:

```text
C01
C02
...
C20
```

Always include corresponding HEX values.

Manufacturer IDs and names are authoritative. When a maker does not publish device-independent HEX values, the stored HEX value is a display/matching reference; physical swatches remain the final authority.

## Common CLI Controls

```bash
uv run python scripts/image_to_pattern.py \
  --input "<SOURCE_IMAGE_PATH>" \
  --output "<TARGET_SVG_PATH>" \
  --mode portrait \
  --brand hama-midi-official \
  --bead-size-mm 5 \
  --preview \
  --a4-pages
```

- `--mode portrait|pet|logo|landscape|art|illustration`: image-specific composition and cleanup policy.
- `--bead-size-mm`: sets both bead diameter and pitch; use `--bead-diameter-mm` / `--bead-pitch-mm` for separate values.
- `--remove-background --background-color '#FFFFFF'`: replace an estimated background with a solid print background.
- `--shopping-list <file.csv|file.json>`: override the companion shopping-list path and format.
- `--report <file.json>`: override the JSON processing-report path. A report is always created.
- `--min-component-size` and `--cleanup-passes`: override the selected mode's cleanup defaults.

## Final Quality Rules

Priority order:

```text
Recognizability
> Physical buildability
> Silhouette
> Expression
> Important color relationships
> Fine detail
> Photographic fidelity
```

A professional Perler pattern is a bead construction blueprint, not merely a pixelated photograph.


## Stateless Skill Execution Contract

This Skill is stateless with respect to user artifacts.

The Skill installation directory MUST NOT be used to store:

- user input images
- generated SVG files
- temporary user artifacts
- conversion history
- exported pattern files

The Skill directory contains only reusable implementation assets such as:

```text
SKILL.md
pyproject.toml
uv.lock
.python-version
scripts/
assets/
tests/
```

### Input Handling

Codex is responsible for resolving the source image path from the current task context.

The image MUST be passed directly to the conversion CLI:

```bash
uv run python <SKILL_DIR>/scripts/image_to_pattern.py \
  --input "<SOURCE_IMAGE_PATH>" \
  --output "<TARGET_SVG_PATH>"
```

Do not copy the source image into the Skill directory.

Do not create an `input/` directory inside the Skill.

### Output Handling

Codex is responsible for choosing the output destination.

Output priority:

1. Path explicitly requested by the user.
2. Current Codex workspace / current working directory.
3. A task-specific writable temporary/workspace directory exposed by Codex.

Never default to the Skill installation directory.

Never create or use:

```text
<SKILL_DIR>/output/
```

for user-generated SVG files.

When no explicit filename is provided, use:

```text
<current-working-directory>/<source-stem>_perler_<width>x<height>.svg
```

or, when Codex prefers organized artifacts:

```text
<current-working-directory>/output/<source-stem>_perler_<width>x<height>.svg
```

The `output/` folder belongs to the user's current workspace, not to the Skill.

When the primary target is `<name>.svg`, companion artifacts default beside it:

```text
<name>_shopping.csv
<name>_report.json
<name>_preview.svg              (with --preview)
<name>_a4_pages/                (with --a4-pages)
```

### Temporary Files

If intermediate files are required:

- prefer in-memory processing;
- otherwise use an OS/Codex temporary directory;
- delete temporary files after successful completion;
- never leave temporary files inside the Skill installation directory.

### Required Codex Behavior

For a request such as:

```text
把这张图转换成拼豆 SVG
```

Codex should:

```text
resolve current image path
→ locate this Skill
→ invoke the Skill script using the image's existing path
→ write SVG and companion artifacts to the current workspace or requested destination
→ validate the SVG and all required quality constraints
→ return the construction SVG, shopping-list, and processing-report paths
```

The Skill MUST behave as a reusable processor, not as a storage location.
