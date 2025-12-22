# Copyright 2025 Dimensional Inc.
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

"""Audio processing operators.

All operators work on raw PCM audio (standard internal format).
Inputs decode to raw, outputs encode from raw.
"""

from dimos.stream.audio2.operators.effects import pitch_shift, ring_modulator, robotize
from dimos.stream.audio2.operators.raw_normalizer import raw_normalizer as normalizer
from dimos.stream.audio2.operators.raw_vumeter import raw_vumeter as vumeter
from dimos.stream.audio2.operators.resample import resample

__all__ = ["normalizer", "vumeter", "robotize", "pitch_shift", "ring_modulator", "resample"]
