#!/usr/bin/env python3
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

"""Example usage of audio operators."""

from dimos.stream.audio2.input.signal import WaveformType, signal
from dimos.stream.audio2.operators.raw_normalizer import raw_normalizer
from dimos.stream.audio2.operators.raw_vumeter import raw_vumeter
from dimos.stream.audio2.output.soundcard import speaker
from dimos.stream.audio2.types import AudioFormat, AudioSpec

# Example 1: VU meter with raw audio playback
print("Example 1: VU meter showing audio levels")
signal(
    waveform=WaveformType.SINE,
    frequency=440.0,
    volume=0.5,
    duration=2.0,
    output=AudioSpec(format=AudioFormat.PCM_F32LE),
).pipe(raw_vumeter(), speaker()).run()

# Example 2: Normalize quiet audio and monitor with VU meter
print("\nExample 2: Normalizing quiet audio with VU meter")
signal(
    waveform=WaveformType.SINE,
    frequency=440.0,
    volume=0.1,  # Very quiet
    duration=2.0,
    output=AudioSpec(format=AudioFormat.PCM_F32LE),
).pipe(
    raw_vumeter(bar_length=30),  # Show input level
    raw_normalizer(target_level=0.8),  # Normalize to 80%
    raw_vumeter(bar_length=30),  # Show output level
    speaker(),
).run()

# Example 3: Use RMS volume for both normalization and metering
print("\nExample 3: RMS-based normalization and metering")
from dimos.stream.audio2.operators.utils import calculate_rms_volume

signal(
    waveform=WaveformType.SINE,
    frequency=440.0,
    volume=0.3,
    duration=2.0,
    output=AudioSpec(format=AudioFormat.PCM_F32LE),
).pipe(
    raw_normalizer(volume_func=calculate_rms_volume, target_level=0.7),
    raw_vumeter(volume_func=calculate_rms_volume),
    speaker(),
).run()
