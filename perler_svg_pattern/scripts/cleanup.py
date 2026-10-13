"""Grid cleanup utilities for physically buildable bead patterns."""

from __future__ import annotations

from collections import Counter, deque

import numpy as np


def _components(grid: np.ndarray):
    height, width = grid.shape
    visited = np.zeros_like(grid, dtype=bool)
    for row in range(height):
        for column in range(width):
            if visited[row, column]:
                continue
            colour = int(grid[row, column])
            queue = deque([(row, column)])
            visited[row, column] = True
            component, border_colours = [], []
            while queue:
                current_row, current_column = queue.popleft()
                component.append((current_row, current_column))
                for row_offset, column_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    next_row, next_column = current_row + row_offset, current_column + column_offset
                    if not (0 <= next_row < height and 0 <= next_column < width):
                        continue
                    if int(grid[next_row, next_column]) != colour:
                        border_colours.append(int(grid[next_row, next_column]))
                    elif not visited[next_row, next_column]:
                        visited[next_row, next_column] = True
                        queue.append((next_row, next_column))
            yield component, border_colours


def cleanup_grid(grid: np.ndarray, *, min_component_size: int = 3, passes: int = 2, protected_mask: np.ndarray | None = None) -> np.ndarray:
    """Merge isolated cells and tiny colour islands into adjacent dominant colours.

    Components smaller than ``min_component_size`` are replaced with their most
    common adjacent colour, including at a grid edge. ``protected_mask`` keeps
    important edge cells intact for portraits, logos, and illustrations.
    """
    result = np.asarray(grid, dtype=np.int16).copy()
    if result.ndim != 2:
        raise ValueError("Grid must be a two-dimensional palette-index array.")
    if protected_mask is not None:
        protected_mask = np.asarray(protected_mask, dtype=bool)
        if protected_mask.shape != result.shape:
            raise ValueError("Protected-mask geometry must match the grid.")
    height, width = result.shape
    for _ in range(max(0, passes)):
        updated = result.copy()
        for component, border_colours in _components(result):
            if len(component) >= min_component_size or not border_colours:
                continue
            if protected_mask is not None and any(protected_mask[row, column] for row, column in component):
                continue
            replacement = Counter(border_colours).most_common(1)[0][0]
            for row, column in component:
                updated[row, column] = replacement
        for row in range(1, height - 1):
            for column in range(1, width - 1):
                if protected_mask is not None and protected_mask[row, column]:
                    continue
                neighbours = [updated[row - 1, column], updated[row + 1, column], updated[row, column - 1], updated[row, column + 1]]
                dominant, count = Counter(neighbours).most_common(1)[0]
                if count >= 3 and updated[row, column] != dominant:
                    updated[row, column] = dominant
        if np.array_equal(updated, result):
            break
        result = updated
    return result
