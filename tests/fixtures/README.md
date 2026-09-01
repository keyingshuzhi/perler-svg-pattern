# Acceptance Fixtures

These small PPM files are deliberately text-based so they can be inspected and
maintained in version control without opaque binary updates.

- `horizontal.ppm`: wide image / landscape acceptance case.
- `vertical.ppm`: tall image / portrait-strategy acceptance case.
- `few_colours.ppm`: logo/pixel-art and low-colour case.
- `no_subject.ppm`: uniform no-subject fallback case.

`tests/test_quality.py` creates a transparent PNG at runtime to cover alpha
flattening without storing generated user-style binary artifacts in the project.
`regression_baselines.json` stores exact palette data plus the SHA-256 grid hash
for deterministic reference scenarios.
