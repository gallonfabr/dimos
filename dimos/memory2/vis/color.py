# Copyright 2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Color mapping utilities for memory2 visualization."""

from __future__ import annotations

import functools


@functools.lru_cache(maxsize=16)
def _cmap(name: str):  # type: ignore[no-untyped-def]
    import matplotlib.pyplot as plt

    return plt.get_cmap(name)


def color(value: float, lo: float = 0.0, hi: float = 1.0, cmap: str = "turbo") -> str:
    """Map a value in [lo, hi] to a hex color string via a matplotlib colormap."""
    t = max(0.0, min(1.0, (value - lo) / (hi - lo))) if hi != lo else 0.5
    r, g, b, _ = _cmap(cmap)(t)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
