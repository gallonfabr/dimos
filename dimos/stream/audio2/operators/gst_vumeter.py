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

"""GStreamer-based VU meter operator.

This VU meter works with any audio format (compressed or raw) by using
GStreamer's level element for measuring audio levels.
"""

import sys
import threading
import time
from typing import Callable, Optional

import gi
import numpy as np

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp
from reactivex import create
from reactivex.abc import ObservableBase

from dimos.stream.audio2.gstreamer import GStreamerPipelineBase
from dimos.stream.audio2.types import AudioEvent, RawAudioEvent, CompressedAudioEvent, AudioSpec
from dimos.stream.audio2.utils import buffer_to_audio_event, validate_pipeline_element
from dimos.utils.logging_config import setup_logger

logger = setup_logger("dimos.stream.audio2.operators.gst_vumeter")


class GStreamerVUMeter(GStreamerPipelineBase):
    """GStreamer-based VU meter using level element."""

    def __init__(
        self,
        threshold: float = 0.01,
        bar_length: int = 50,
        show_percentage: bool = True,
        show_activity: bool = True,
        level_interval_ms: int = 50,
        use_rms: bool = False,
    ):
        super().__init__()

        # VU meter parameters
        self.threshold = threshold
        self.bar_length = bar_length
        self.show_percentage = show_percentage
        self.show_activity = show_activity
        self.level_interval_ms = level_interval_ms
        self.use_rms = use_rms

        # Pipeline elements
        self._appsrc: Optional[GstApp.AppSrc] = None
        self._appsink: Optional[GstApp.AppSink] = None
        self._level: Optional[Gst.Element] = None

        # VU meter state
        self._activity_count = 0
        self._total_count = 0
        self._display_lock = threading.Lock()

        # Input/output format tracking
        self._input_format: Optional[AudioSpec] = None
        self._output_rate: Optional[int] = None
        self._output_channels: Optional[int] = None

        # Threading
        self._pull_thread: Optional[threading.Thread] = None
        self._observer = None

    def _display_vu_meter(self, structure):
        """Display VU meter based on level measurements."""
        try:
            # Get values from level element
            if self.use_rms:
                # Use RMS values
                level_values = structure.get_value("rms")
            else:
                # Use peak values
                level_values = structure.get_value("peak")

            if not level_values:
                return

            # Convert dB to linear scale and find max across channels
            max_level_db = max(level_values)

            # Convert dB to linear: linear = 10^(dB/20)
            if max_level_db > -200:  # Ignore silence (-inf dB)
                volume = pow(10.0, max_level_db / 20.0)
            else:
                volume = 0.0

            with self._display_lock:
                self._total_count += 1
                if volume > self.threshold:
                    self._activity_count += 1

                # Build VU meter display
                filled = int(volume * self.bar_length)
                filled = min(filled, self.bar_length)
                bar = "█" * filled + "░" * (self.bar_length - filled)

                # Build output string
                output_parts = [bar]

                if self.show_percentage:
                    percentage = int(volume * 100)
                    output_parts.append(f" {percentage:3d}%")

                if self.show_activity:
                    activity_pct = (
                        int((self._activity_count / self._total_count) * 100)
                        if self._total_count > 0
                        else 0
                    )
                    output_parts.append(f" active")

                # Print with carriage return (overwrite same line)
                output = "".join(output_parts)
                print(f"\r{output}", end="", file=sys.stderr, flush=True)

        except Exception as e:
            logger.error(f"Error displaying VU meter: {e}")

    def _on_bus_message(self, bus, message):
        """Handle bus messages, particularly from level element."""
        # Call parent handler first
        super()._on_bus_message(bus, message)

        # Handle level messages
        if message.type == Gst.MessageType.ELEMENT:
            structure = message.get_structure()
            if structure and structure.get_name() == "level":
                self._display_vu_meter(structure)

    def _create_pipeline(self):
        """Create the GStreamer pipeline: appsrc ! decodebin ! audioconvert ! level ! appsink."""

        # Build pipeline string
        pipeline_str = (
            "appsrc name=src ! "
            "decodebin ! "
            "audioconvert ! "
            "audio/x-raw,format=F32LE ! "  # Convert to float32 for level
            "level name=level ! "
            "appsink name=sink"
        )

        logger.debug(f"Creating VU meter pipeline: {pipeline_str}")
        self._pipeline = Gst.parse_launch(pipeline_str)

        # Get elements
        self._appsrc = validate_pipeline_element(self._pipeline, "src")
        self._appsink = validate_pipeline_element(self._pipeline, "sink")
        self._level = validate_pipeline_element(self._pipeline, "level")

        # Configure appsrc
        self._appsrc.set_property("is-live", False)
        self._appsrc.set_property("format", Gst.Format.TIME)
        self._appsrc.set_property("block", False)

        # Configure appsink
        self._appsink.set_property("emit-signals", True)
        self._appsink.set_property("sync", False)

        # Configure level element
        interval_ns = self.level_interval_ms * 1000000  # Convert ms to ns
        self._level.set_property("interval", interval_ns)
        self._level.set_property("post-messages", True)

        # Set up bus
        self._setup_bus(self._pipeline)

    def _push_event_to_pipeline(self, event: AudioEvent):
        """Push an AudioEvent to the pipeline via appsrc."""
        # Set caps on first event
        if self._input_format is None:
            self._input_format = AudioSpec(
                format=event.format, sample_rate=event.sample_rate, channels=event.channels
            )
            caps_str = self._input_format.to_gst_caps_string()
            if "layout=" not in caps_str:
                caps_str += ",layout=interleaved"
            caps = Gst.Caps.from_string(caps_str)
            self._appsrc.set_property("caps", caps)
            logger.info(f"Set input caps: {caps_str}")

        # Create buffer
        if isinstance(event, RawAudioEvent):
            if event.channels > 1:
                data = np.ascontiguousarray(event.data)
            else:
                data = event.data
            buffer = Gst.Buffer.new_wrapped(data.tobytes())
        elif isinstance(event, CompressedAudioEvent):
            buffer = Gst.Buffer.new_wrapped(event.data)
        else:
            logger.warning(f"Unknown event type: {type(event)}")
            return

        # Set timestamp
        buffer.pts = int(event.timestamp * Gst.SECOND)

        # Push to pipeline
        ret = self._appsrc.emit("push-buffer", buffer)
        if ret != Gst.FlowReturn.OK:
            logger.warning(f"Failed to push buffer: {ret}")

    def _pull_from_pipeline(self):
        """Pull processed samples from appsink and emit as AudioEvents."""
        logger.debug("Pull thread starting")

        buffer_count = 0
        try:
            while self._running:
                sample = self._appsink.emit("pull-sample")
                if sample is None:
                    if not self._running:
                        break
                    time.sleep(0.001)
                    continue

                buffer = sample.get_buffer()
                if buffer is None:
                    continue

                # Parse caps on first sample
                if self._output_rate is None:
                    caps = sample.get_caps()
                    if caps:
                        structure = caps.get_structure(0)
                        self._output_rate = structure.get_int("rate")[1]
                        self._output_channels = structure.get_int("channels")[1]
                        logger.info(
                            f"Output format: {self._output_rate}Hz, {self._output_channels}ch"
                        )

                # Convert to AudioEvent
                from dimos.stream.audio2.types import AudioFormat

                output_spec = AudioSpec(
                    format=AudioFormat.PCM_F32LE,
                    sample_rate=self._output_rate,
                    channels=self._output_channels,
                )

                event = buffer_to_audio_event(
                    buffer=buffer,
                    spec=output_spec,
                    detected_rate=self._output_rate,
                    detected_channels=self._output_channels,
                )

                buffer_count += 1

                if self._observer:
                    self._observer.on_next(event)

        except Exception as e:
            logger.error(f"Pull thread error: {e}")
            if self._observer:
                self._observer.on_error(e)

        finally:
            logger.info(f"Pull thread exiting (processed {buffer_count} buffers)")
            # Print newline to move past the VU meter display
            print(file=sys.stderr)

    def process_observable(self, source: ObservableBase) -> ObservableBase:
        """Process an observable of AudioEvents through the VU meter."""

        def subscribe(observer, scheduler=None):
            self._observer = observer

            try:
                # Ensure mainloop is running
                self._ensure_pipeline_ready()
                self._create_pipeline()

                # Start pipeline
                ret = self._pipeline.set_state(Gst.State.PLAYING)
                if ret == Gst.StateChangeReturn.FAILURE:
                    raise RuntimeError("Failed to start pipeline")

                # Start pull thread
                self._pull_thread = threading.Thread(
                    target=self._pull_from_pipeline, daemon=True, name="GstVUMeter-pull"
                )
                self._pull_thread.start()

                method = "rms" if self.use_rms else "peak"
                logger.info(f"GStreamer VU meter started (method: {method})")

                # Subscribe to source and push events to pipeline
                def on_next(event):
                    self._push_event_to_pipeline(event)

                def on_error(error):
                    logger.error(f"Source error: {error}")
                    self._cleanup_pipeline()
                    observer.on_error(error)

                def on_completed():
                    logger.info("Source completed, sending EOS")
                    if self._appsrc:
                        self._appsrc.emit("end-of-stream")
                    # Wait a bit for pipeline to finish processing
                    time.sleep(0.1)
                    self._running = False
                    if self._pull_thread:
                        self._pull_thread.join(timeout=2.0)
                    observer.on_completed()
                    self._cleanup_pipeline()

                source.subscribe(on_next, on_error, on_completed, scheduler=scheduler)

            except Exception as e:
                observer.on_error(e)
                self._cleanup_pipeline()

            def dispose():
                logger.info("Disposing GStreamer VU meter")
                self._running = False
                if self._pipeline:
                    self._pipeline.set_state(Gst.State.NULL)
                if self._pull_thread:
                    self._pull_thread.join(timeout=2.0)
                self._cleanup_pipeline()

            from reactivex import disposable

            return disposable.Disposable(dispose)

        return create(subscribe)


def vumeter(
    threshold: float = 0.01,
    bar_length: int = 50,
    show_percentage: bool = True,
    show_activity: bool = True,
    level_interval_ms: int = 50,
    use_rms: bool = False,
):
    """Create a GStreamer-based VU meter operator that displays audio levels.

    This operator displays a visual representation of audio volume to the console
    while passing audio events through unchanged. Works with both raw and compressed
    audio formats by automatically decoding.

    Args:
        threshold: Minimum volume to consider as "active" (default: 0.01)
        bar_length: Length of the VU meter bar in characters (default: 50)
        show_percentage: Show volume percentage (default: True)
        show_activity: Show activity indicator (default: True)
        level_interval_ms: Interval for level measurements in milliseconds (default: 50)
        use_rms: Use RMS instead of peak for measurements (default: False)

    Returns:
        An operator function that can be used with pipe()

    Examples:
        # Monitor compressed audio levels
        file_input("audio.mp3").pipe(
            vumeter(),
            speaker()
        ).run()

        # Use RMS with custom bar length
        microphone().pipe(
            vumeter(bar_length=80, use_rms=True),
            speaker()
        ).run()

        # Minimal meter without percentage and activity
        file_input("podcast.opus").pipe(
            vumeter(show_percentage=False, show_activity=False)
        ).run()
    """

    meter = GStreamerVUMeter(
        threshold=threshold,
        bar_length=bar_length,
        show_percentage=show_percentage,
        show_activity=show_activity,
        level_interval_ms=level_interval_ms,
        use_rms=use_rms,
    )

    def _vumeter(source: ObservableBase) -> ObservableBase:
        return meter.process_observable(source)

    return _vumeter
