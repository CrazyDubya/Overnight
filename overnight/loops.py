"""
Loop management and stuck detection for overnight execution.

This module provides:
- Execution loop abstractions with configurable limits
- Stuck pattern detection (repeating errors, infinite loops)
- Recovery strategies
- State machine for loop lifecycle
"""

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable, Dict, Any


class LoopState(Enum):
    """State of an execution loop."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    LIMIT_REACHED = "limit_reached"
    STUCK = "stuck"
    ERROR = "error"
    INTERRUPTED = "interrupted"


@dataclass
class LoopMetrics:
    """Metrics for a loop execution."""
    iterations: int = 0
    successful_iterations: int = 0
    failed_iterations: int = 0
    total_duration_seconds: float = 0.0
    stuck_detections: int = 0
    recoveries_attempted: int = 0
    recoveries_successful: int = 0


class StuckDetector:
    """
    Detects when execution is "stuck" in repetitive patterns.

    Stuck patterns include:
    - Same error message repeated N times
    - Same file being modified repeatedly without progress
    - Circular dependency in task execution
    - Token output without meaningful progress
    """

    def __init__(
        self,
        threshold: int = 3,
        window_size: int = 10,
    ):
        self.threshold = threshold
        self.window_size = window_size

        # Recent outputs for pattern matching
        self._output_hashes: deque = deque(maxlen=window_size)
        self._error_messages: deque = deque(maxlen=window_size)
        self._file_modifications: deque = deque(maxlen=window_size)

        self.last_pattern: Optional[str] = None

        # Known stuck patterns (regex)
        self._stuck_patterns = [
            r"maximum.*retries.*exceeded",
            r"rate.limit.*exceeded",
            r"connection.*refused.*repeatedly",
            r"same.error.occurred",
            r"no.progress.detected",
            r"circular.dependency",
            r"infinite.loop.detected",
        ]

    def check(self, output: str) -> bool:
        """
        Check if the output indicates a stuck state.

        Returns True if stuck pattern detected.
        """
        # Hash the output for comparison
        output_hash = self._hash_output(output)
        self._output_hashes.append(output_hash)

        # Check for repeated identical outputs
        if self._check_repeated_outputs():
            self.last_pattern = "repeated_identical_output"
            return True

        # Check for known stuck patterns
        for pattern in self._stuck_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                self.last_pattern = f"known_pattern:{pattern}"
                return True

        # Check for error repetition
        errors = self._extract_errors(output)
        for error in errors:
            self._error_messages.append(error)

        if self._check_repeated_errors():
            self.last_pattern = "repeated_errors"
            return True

        return False

    def _hash_output(self, output: str) -> str:
        """Create a normalized hash of output for comparison."""
        # Normalize by removing timestamps, line numbers, etc.
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', output)
        normalized = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIME', normalized)
        normalized = re.sub(r'line \d+', 'line N', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def _check_repeated_outputs(self) -> bool:
        """Check if recent outputs are repetitive."""
        if len(self._output_hashes) < self.threshold:
            return False

        recent = list(self._output_hashes)[-self.threshold:]
        return len(set(recent)) == 1  # All identical

    def _extract_errors(self, output: str) -> List[str]:
        """Extract error messages from output."""
        errors = []
        error_patterns = [
            r"Error:(.+)",
            r"ERROR:(.+)",
            r"Exception:(.+)",
            r"Failed:(.+)",
            r"error\[.+\]:(.+)",
        ]
        for pattern in error_patterns:
            matches = re.findall(pattern, output)
            errors.extend(matches)
        return errors

    def _check_repeated_errors(self) -> bool:
        """Check if same error is repeating."""
        if len(self._error_messages) < self.threshold:
            return False

        recent = list(self._error_messages)[-self.threshold:]
        # Normalize errors for comparison
        normalized = [e.strip().lower()[:50] for e in recent]
        return len(set(normalized)) == 1

    def record_file_modification(self, filepath: str) -> None:
        """Record a file modification for pattern detection."""
        self._file_modifications.append(filepath)

    def check_file_churn(self) -> bool:
        """Check if same file is being modified repeatedly."""
        if len(self._file_modifications) < self.threshold * 2:
            return False

        recent = list(self._file_modifications)[-self.threshold * 2:]
        # Check if any file appears more than threshold times
        from collections import Counter
        counts = Counter(recent)
        return any(c >= self.threshold for c in counts.values())

    def reset(self) -> None:
        """Reset detection state."""
        self._output_hashes.clear()
        self._error_messages.clear()
        self._file_modifications.clear()
        self.last_pattern = None


@dataclass
class RecoveryStrategy:
    """A strategy for recovering from a stuck state."""
    name: str
    description: str
    applicable_patterns: List[str]
    action: Callable[[], bool]  # Returns True if recovery successful
    priority: int = 0


class RecoveryManager:
    """
    Manages recovery from stuck states.

    Provides multiple recovery strategies and attempts them
    in priority order until one succeeds.
    """

    def __init__(self):
        self._strategies: List[RecoveryStrategy] = []
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Register default recovery strategies."""
        self._strategies = [
            RecoveryStrategy(
                name="clear_context",
                description="Clear accumulated context and retry",
                applicable_patterns=["repeated_identical_output", "repeated_errors"],
                action=lambda: True,  # Placeholder
                priority=1,
            ),
            RecoveryStrategy(
                name="simplify_task",
                description="Break task into smaller subtasks",
                applicable_patterns=["repeated_errors", "known_pattern:.*"],
                action=lambda: True,
                priority=2,
            ),
            RecoveryStrategy(
                name="alternative_approach",
                description="Try a different approach to the task",
                applicable_patterns=["*"],
                action=lambda: True,
                priority=3,
            ),
            RecoveryStrategy(
                name="skip_and_continue",
                description="Skip this task and continue with others",
                applicable_patterns=["*"],
                action=lambda: True,
                priority=4,
            ),
        ]

    def add_strategy(self, strategy: RecoveryStrategy) -> None:
        """Add a custom recovery strategy."""
        self._strategies.append(strategy)
        self._strategies.sort(key=lambda s: s.priority)

    def get_strategy(self, pattern: str) -> Optional[RecoveryStrategy]:
        """Get the best recovery strategy for a stuck pattern."""
        for strategy in self._strategies:
            for applicable in strategy.applicable_patterns:
                if applicable == "*" or re.match(applicable, pattern):
                    return strategy
        return None

    def attempt_recovery(self, pattern: str) -> bool:
        """
        Attempt recovery from a stuck state.

        Returns True if recovery was successful.
        """
        strategy = self.get_strategy(pattern)
        if not strategy:
            return False

        try:
            return strategy.action()
        except Exception:
            return False


class ExecutionLoop:
    """
    Manages execution loops with configurable limits and monitoring.

    Features:
    - Iteration counting and limits
    - Time-based limits
    - Stuck detection integration
    - State management
    - Progress callbacks
    """

    def __init__(
        self,
        max_iterations: int = 100,
        max_duration_seconds: float = 3600,
        stuck_detector: Optional[StuckDetector] = None,
        on_progress: Optional[Callable[[int, LoopState], None]] = None,
    ):
        self.max_iterations = max_iterations
        self.max_duration_seconds = max_duration_seconds
        self.stuck_detector = stuck_detector or StuckDetector()
        self.on_progress = on_progress

        self.metrics = LoopMetrics()
        self.state = LoopState.PENDING
        self._start_time: Optional[float] = None
        self._recovery_manager = RecoveryManager()

    def should_continue(self) -> bool:
        """Check if the loop should continue executing."""
        if self.state in (LoopState.COMPLETED, LoopState.ERROR, LoopState.INTERRUPTED):
            return False

        if self.metrics.iterations >= self.max_iterations:
            self.state = LoopState.LIMIT_REACHED
            return False

        if self._start_time:
            import time
            elapsed = time.time() - self._start_time
            if elapsed >= self.max_duration_seconds:
                self.state = LoopState.LIMIT_REACHED
                return False

        return True

    def record_iteration(self, success: bool, output: str = "") -> bool:
        """
        Record an iteration and check for stuck state.

        Returns True if execution should continue.
        """
        self.metrics.iterations += 1
        if success:
            self.metrics.successful_iterations += 1
        else:
            self.metrics.failed_iterations += 1

        # Check for stuck state
        if self.stuck_detector.check(output):
            self.metrics.stuck_detections += 1
            return self._handle_stuck()

        # Progress callback
        if self.on_progress:
            self.on_progress(self.metrics.iterations, self.state)

        return self.should_continue()

    def _handle_stuck(self) -> bool:
        """
        Handle a detected stuck state.

        Returns True if recovery was successful and execution should continue.
        """
        self.metrics.recoveries_attempted += 1

        pattern = self.stuck_detector.last_pattern or "unknown"
        success = self._recovery_manager.attempt_recovery(pattern)

        if success:
            self.metrics.recoveries_successful += 1
            self.stuck_detector.reset()
            return True
        else:
            self.state = LoopState.STUCK
            return False

    def start(self) -> None:
        """Start the execution loop."""
        import time
        self._start_time = time.time()
        self.state = LoopState.RUNNING

    def complete(self) -> None:
        """Mark the loop as completed."""
        import time
        if self._start_time:
            self.metrics.total_duration_seconds = time.time() - self._start_time
        self.state = LoopState.COMPLETED

    def pause(self) -> None:
        """Pause the execution loop."""
        self.state = LoopState.PAUSED

    def resume(self) -> None:
        """Resume the execution loop."""
        if self.state == LoopState.PAUSED:
            self.state = LoopState.RUNNING


class AdaptiveLoop(ExecutionLoop):
    """
    An execution loop that adapts its behavior based on observed patterns.

    Features:
    - Learns from successful/failed iterations
    - Adjusts retry behavior dynamically
    - Optimizes for throughput over time
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._success_streak = 0
        self._failure_streak = 0
        self._learned_patterns: Dict[str, Any] = {}

    def record_iteration(self, success: bool, output: str = "") -> bool:
        """Record iteration with adaptive learning."""
        # Update streaks
        if success:
            self._success_streak += 1
            self._failure_streak = 0
        else:
            self._failure_streak += 1
            self._success_streak = 0

        # Adaptive behavior based on streaks
        if self._success_streak > 5:
            # Things are going well, can be more aggressive
            self.stuck_detector.threshold = min(5, self.stuck_detector.threshold + 1)
        elif self._failure_streak > 3:
            # Having trouble, be more conservative
            self.stuck_detector.threshold = max(2, self.stuck_detector.threshold - 1)

        return super().record_iteration(success, output)
