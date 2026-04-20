"""dimos - A fork of dimensionalOS/dimos.

A framework for building and deploying autonomous robot agents
with multimodal perception, planning, and action capabilities.

Personal fork: tracking upstream at dimensionalOS/dimos for learning purposes.
Fork notes: experimenting with custom agent configurations and perception pipelines.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dimos")
except PackageNotFoundError:
    __version__ = "0.0.0"

__author__ = "dimos contributors"
__license__ = "Apache-2.0"
__upstream__ = "https://github.com/dimensionalOS/dimos"
# Upstream sync: periodically rebase against upstream main to stay current
__fork_purpose__ = "personal learning and experimentation"

__all__ = ["__version__", "__author__", "__license__", "__upstream__", "__fork_purpose__"]
