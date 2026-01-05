"""
Overnight - A harness to run Claude Code autonomously overnight.

This module provides the infrastructure for running Claude Code in
unattended mode with proper oversight, loop detection, progress tracking,
and graceful degradation when human input would normally be required.
"""

__version__ = "0.1.0"

from .harness import OvernightHarness
from .oversight import OversightManager
from .loops import ExecutionLoop, StuckDetector
from .encouragement import OvernightPrompts

__all__ = [
    "OvernightHarness",
    "OversightManager",
    "ExecutionLoop",
    "StuckDetector",
    "OvernightPrompts",
]
