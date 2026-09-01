# Palettes

This directory contains maintained, source-documented physical bead palettes.

- `perler-midi-open-stock-2025.json`: Perler open-stock IDs and names from its 2025 reference.
- `hama-midi-official.json`: Hama Midi IDs and names from the official colour chart.
- `artkal-s-midi-official.json`: Artkal S / 5 mm IDs and RGB values from the official 225-colour chart.

Each JSON file stores an official source URL and retrieval date. Brand IDs/names are
verified against the source; where a maker does not publish device-independent
colour values, `hex` is explicitly a display/matching reference rather than a
guarantee of the physical bead colour. Refresh a file from its linked official
source before making a commercial purchasing decision.

Place additional verified physical bead palette files here.

Recommended formats:

- JSON
- CSV

Example conceptual fields:

```json
{
  "id": "C01",
  "name": "Black",
  "hex": "#000000"
}
```

Do not invent commercial bead brand color codes.
