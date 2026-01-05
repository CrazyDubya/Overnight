"""
Oversight and monitoring for overnight Claude Code execution.

This module provides:
- Structured logging with severity levels
- Checkpointing for resume capability
- Progress tracking and metrics
- Decision audit trail
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class CheckpointData:
    """Data structure for checkpoints."""
    timestamp: str
    tasks_total: int
    tasks_completed: int
    results: List[Dict[str, Any]]
    state: str
    tasks: List[str] = field(default_factory=list)  # Full task list for resume
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionRecord:
    """Record of an autonomous decision made during overnight operation."""
    timestamp: str
    decision_type: str  # "proceed", "skip", "retry", "abort"
    risk_level: str  # "low", "medium", "high"
    context: str
    reasoning: str
    outcome: Optional[str] = None


class OversightManager:
    """
    Manages oversight, logging, and checkpointing for overnight runs.

    Key responsibilities:
    - Maintain audit log of all actions and decisions
    - Save/load checkpoints for resume capability
    - Track metrics and progress
    - Generate oversight reports
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        log_file: Optional[str] = None,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._logs: List[str] = []
        self._decisions: List[DecisionRecord] = []
        self._metrics: Dict[str, Any] = {
            "start_time": None,
            "tokens_used": 0,
            "files_modified": [],
            "commands_run": [],
            "errors_encountered": [],
        }

        # Setup logging
        self._setup_logging(log_file)

    def _setup_logging(self, log_file: Optional[str]) -> None:
        """Configure logging infrastructure."""
        self.logger = logging.getLogger("overnight")
        self.logger.setLevel(logging.DEBUG)

        # Console handler
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
        self.logger.addHandler(console)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            ))
            self.logger.addHandler(file_handler)

        # Also log to checkpoint dir
        run_log = self.checkpoint_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(run_log)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        self.logger.addHandler(file_handler)

    def log(self, level: str, message: str) -> None:
        """Log a message with the specified level."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}"
        self._logs.append(log_entry)

        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)

    def get_logs(self) -> List[str]:
        """Get all log entries."""
        return self._logs.copy()

    def record_decision(
        self,
        decision_type: str,
        risk_level: str,
        context: str,
        reasoning: str,
    ) -> DecisionRecord:
        """Record an autonomous decision for audit purposes."""
        decision = DecisionRecord(
            timestamp=datetime.now().isoformat(),
            decision_type=decision_type,
            risk_level=risk_level,
            context=context,
            reasoning=reasoning,
        )
        self._decisions.append(decision)
        self.log("INFO", f"Decision: {decision_type} ({risk_level} risk) - {context[:50]}...")
        return decision

    def update_decision_outcome(self, decision: DecisionRecord, outcome: str) -> None:
        """Update a decision record with its outcome."""
        decision.outcome = outcome
        self.log("INFO", f"Decision outcome: {outcome}")

    def save_checkpoint(self, data: CheckpointData) -> Path:
        """Save a checkpoint for resume capability."""
        checkpoint_file = self.checkpoint_dir / "latest_checkpoint.json"

        # Also save timestamped version
        timestamped = self.checkpoint_dir / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        checkpoint_data = {
            **data.__dict__,
            "decisions": [d.__dict__ for d in self._decisions],
            "metrics": self._metrics,
        }

        for path in [checkpoint_file, timestamped]:
            with open(path, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

        self.log("DEBUG", f"Checkpoint saved: {checkpoint_file}")
        return checkpoint_file

    def load_checkpoint(self) -> Optional[CheckpointData]:
        """Load the latest checkpoint."""
        checkpoint_file = self.checkpoint_dir / "latest_checkpoint.json"

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file) as f:
            data = json.load(f)

        return CheckpointData(
            timestamp=data["timestamp"],
            tasks_total=data["tasks_total"],
            tasks_completed=data["tasks_completed"],
            results=data["results"],
            state=data["state"],
            tasks=data.get("tasks", []),
            metadata=data.get("metadata", {}),
        )

    def track_metric(self, name: str, value: Any) -> None:
        """Track a metric value."""
        if name not in self._metrics:
            self._metrics[name] = value
        elif isinstance(self._metrics[name], list):
            self._metrics[name].append(value)
        elif isinstance(self._metrics[name], (int, float)):
            self._metrics[name] += value
        else:
            self._metrics[name] = value

    def get_metrics(self) -> Dict[str, Any]:
        """Get all tracked metrics."""
        return self._metrics.copy()

    def generate_oversight_report(self) -> str:
        """Generate a detailed oversight report."""
        lines = [
            "=" * 60,
            "OVERNIGHT OVERSIGHT REPORT",
            "=" * 60,
            "",
            "DECISIONS MADE AUTONOMOUSLY:",
            "-" * 40,
        ]

        if not self._decisions:
            lines.append("  (No autonomous decisions recorded)")
        else:
            for d in self._decisions:
                lines.extend([
                    f"  [{d.timestamp}]",
                    f"    Type: {d.decision_type}",
                    f"    Risk: {d.risk_level}",
                    f"    Context: {d.context[:80]}...",
                    f"    Reasoning: {d.reasoning[:80]}...",
                    f"    Outcome: {d.outcome or 'pending'}",
                    "",
                ])

        lines.extend([
            "",
            "METRICS:",
            "-" * 40,
        ])

        for name, value in self._metrics.items():
            if isinstance(value, list):
                lines.append(f"  {name}: {len(value)} items")
            else:
                lines.append(f"  {name}: {value}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)


class ProgressTracker:
    """
    Tracks and visualizes progress during overnight execution.

    Provides:
    - Real-time progress updates
    - ETA calculations
    - Throughput metrics
    """

    def __init__(self, total_tasks: int):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.start_time = datetime.now()
        self.task_times: List[float] = []

    def task_completed(self, duration_seconds: float) -> None:
        """Record task completion."""
        self.completed_tasks += 1
        self.task_times.append(duration_seconds)

    @property
    def progress_percent(self) -> float:
        """Current progress as percentage."""
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def avg_task_time(self) -> float:
        """Average time per task in seconds."""
        if not self.task_times:
            return 0.0
        return sum(self.task_times) / len(self.task_times)

    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        remaining = self.total_tasks - self.completed_tasks
        return remaining * self.avg_task_time

    @property
    def elapsed_seconds(self) -> float:
        """Elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def status_line(self) -> str:
        """Generate a status line for display."""
        eta_min = self.eta_seconds / 60
        elapsed_min = self.elapsed_seconds / 60

        return (
            f"Progress: {self.completed_tasks}/{self.total_tasks} "
            f"({self.progress_percent:.0f}%) | "
            f"Elapsed: {elapsed_min:.1f}m | "
            f"ETA: {eta_min:.1f}m"
        )
