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

"""Example usage of the audio2 streaming API."""

from dimos.stream.audio2.input.file import file_input
from dimos.stream.audio2.input.microphone import microphone
from dimos.stream.audio2.input.signal import signal, WaveformType
from dimos.stream.audio2.output.soundcard import speaker
from dimos.stream.audio2.types import AudioFormat, AudioSpec

# Example 1: Play a test signal through speakers
signal(frequency=440.0, duration=2.0).pipe(speaker()).run()

# Example 2: Play an audio file
file_input("audio.wav").pipe(speaker()).run()

# Example 3: Microphone passthrough to speakers
microphone().pipe(speaker()).run()

# Example 4: Generate white noise
signal(waveform=WaveformType.WHITE_NOISE, volume=0.3, duration=1.0).pipe(speaker()).run()

# Example 5: Process audio with operators
from reactivex import operators as ops

signal(frequency=440.0, duration=1.0).pipe(
    ops.map(lambda event: event),  # Add custom processing here
    speaker(),
).run()
