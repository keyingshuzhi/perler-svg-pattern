# syntax=docker/dockerfile:1
# perler-svg-pattern — containerised MCP server for魔塔 (ModelScope) deployment.
#
# Build:
#   docker build -t perler-svg-pattern:0.2.1 .
#
# Run (stdio MCP transport, as expected by desktop MCP clients and魔塔):
#   docker run --rm -i perler-svg-pattern:0.2.1
#
# The image is deliberately minimal: the heavy image-processing dependencies
# (Pillow, NumPy, OpenCV, scikit-learn) are declared in pyproject.toml and
# installed by uv into a .venv that is NOT shipped in the image.  At runtime
# the entrypoint uses `uvx`-style isolation so the container can be re-tagged
# without rebuilding the dependency tree.

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy

# Install uv and required system libraries for OpenCV / Pillow.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgl1 \
        libglib2.0-0 \
        && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy only the dependency manifests first for layer caching.
COPY pyproject.toml uv.lock ./
COPY README.md LICENSE ./

# Install the project and its dependencies into the system Python.
RUN uv pip install --python /usr/local/bin/python \
    "perler-svg-pattern==0.2.1" \
    "mcp[cli]>=2,<3" \
    "pillow>=11.0,<13" \
    "numpy>=2.1,<3" \
    "opencv-python-headless>=4.10,<5" \
    "scikit-learn>=1.6,<2"

# Copy the package source (needed for the shipped palettes and scripts).
COPY perler_svg_pattern/ ./perler_svg_pattern/
COPY assets/palettes/ ./assets/palettes/

# Verify the install and the MCP handshake.
RUN python -c "import perler_svg_pattern; print('perler-svg-pattern', perler_svg_pattern.__version__)" \
    && python -c "from perler_svg_pattern.scripts.palette import builtin_palette_names; print('palettes:', builtin_palette_names())"

# Default command: serve the MCP server over stdio.
ENTRYPOINT ["python", "-m", "perler_svg_pattern"]