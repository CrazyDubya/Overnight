"""
Core harness for overnight Claude Code execution.

The harness orchestrates autonomous operation by:
1. Managing execution loops with configurable limits
2. Providing oversight and progress tracking
3. Handling stuck detection and recovery
4. Generating morning reports
"""

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .oversight import OversightManager, CheckpointData
from .loops import ExecutionLoop, StuckDetector, LoopState
from .encouragement import OvernightPrompts


@dataclass
class OvernightConfig:
    """Configuration for overnight operation."""

    # Time limits
    max_runtime_hours: float = 8.0
    max_idle_minutes: float = 30.0

    # Iteration limits
    max_task_retries: int = 3
    max_total_iterations: int = 1000

    # Stuck detection
    stuck_threshold: int = 3  # Same error N times = stuck
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 300.0

    # Scope boundaries
    protected_paths: List[str] = field(default_factory=list)
    allowed_commands: Optional[List[str]] = None  # None = all allowed

    # Checkpointing
    checkpoint_interval_minutes: float = 5.0
    checkpoint_dir: str = ".overnight"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Risk tolerance (1-5, where 1 is most conservative)
    risk_tolerance: int = 2

    @classmethod
    def from_file(cls, path: Path) -> "OvernightConfig":
        """Load configuration from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def to_file(self, path: Path) -> None:
        """Save configuration to JSON file."""
        with open(path, "w") as f:
            json.dump(self.__dict__, f, indent=2)


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    output: str
    error: Optional[str] = None
    duration_seconds: float = 0.0
    retries: int = 0
    decisions_made: List[Dict[str, Any]] = field(default_factory=list)


class OvernightHarness:
    """
    Main harness for running Claude Code overnight.

    The harness wraps Claude Code execution with:
    - Progress tracking and checkpointing
    - Stuck detection and recovery
    - Configurable guardrails and limits
    - Morning report generation

    Example usage:
        config = OvernightConfig(max_runtime_hours=6)
        harness = OvernightHarness(config)

        harness.add_task("Fix all type errors in src/")
        harness.add_task("Run test suite and fix failures")

        report = harness.run()
        print(report.summary())
    """

    def __init__(
        self,
        config: Optional[OvernightConfig] = None,
        working_dir: Optional[Path] = None,
    ):
        self.config = config or OvernightConfig()
        self.working_dir = working_dir or Path.cwd()

        # Initialize components
        self.oversight = OversightManager(
            checkpoint_dir=self.working_dir / self.config.checkpoint_dir,
            log_file=self.config.log_file,
        )
        self.stuck_detector = StuckDetector(
            threshold=self.config.stuck_threshold
        )
        self.prompts = OvernightPrompts(
            risk_tolerance=self.config.risk_tolerance
        )

        # State
        self.tasks: List[str] = []
        self.results: List[TaskResult] = []
        self.start_time: Optional[datetime] = None
        self.state = LoopState.PENDING

    def add_task(self, task: str) -> None:
        """Add a task to the overnight queue."""
        self.tasks.append(task)
        self.oversight.log("INFO", f"Task added: {task[:100]}...")

    def add_tasks(self, tasks: List[str]) -> None:
        """Add multiple tasks to the overnight queue."""
        for task in tasks:
            self.add_task(task)

    def _check_limits(self) -> Optional[str]:
        """Check if any limits have been exceeded. Returns reason if so."""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            max_runtime = timedelta(hours=self.config.max_runtime_hours)
            if elapsed > max_runtime:
                return f"Max runtime exceeded ({self.config.max_runtime_hours}h)"

        total_iterations = sum(r.retries + 1 for r in self.results)
        if total_iterations >= self.config.max_total_iterations:
            return f"Max iterations exceeded ({self.config.max_total_iterations})"

        return None

    def _execute_task(self, task: str) -> TaskResult:
        """Execute a single task with retry logic."""
        task_id = f"task_{len(self.results)}_{int(time.time())}"
        start = time.time()
        retries = 0
        decisions = []

        while retries <= self.config.max_task_retries:
            try:
                # Build the overnight-aware prompt
                prompt = self.prompts.wrap_task(
                    task,
                    context={
                        "retry_count": retries,
                        "elapsed_hours": self._elapsed_hours(),
                        "tasks_completed": len([r for r in self.results if r.success]),
                        "tasks_remaining": len(self.tasks) - len(self.results),
                    }
                )

                # Execute via Claude Code CLI
                result = self._run_claude_code(prompt)

                # Check for stuck patterns
                if self.stuck_detector.check(result.get("output", "")):
                    raise StuckError(f"Stuck pattern detected: {self.stuck_detector.last_pattern}")

                return TaskResult(
                    task_id=task_id,
                    success=result.get("success", False),
                    output=result.get("output", ""),
                    error=result.get("error"),
                    duration_seconds=time.time() - start,
                    retries=retries,
                    decisions_made=decisions,
                )

            except StuckError as e:
                self.oversight.log("WARNING", f"Stuck detected: {e}")
                # Try recovery
                recovery_action = self.prompts.get_recovery_suggestion(str(e))
                decisions.append({
                    "type": "recovery",
                    "reason": str(e),
                    "action": recovery_action,
                })
                retries += 1
                self._backoff(retries)

            except Exception as e:
                self.oversight.log("ERROR", f"Task error: {e}")
                retries += 1
                self._backoff(retries)

        # All retries exhausted
        return TaskResult(
            task_id=task_id,
            success=False,
            output="",
            error=f"Max retries ({self.config.max_task_retries}) exceeded",
            duration_seconds=time.time() - start,
            retries=retries,
            decisions_made=decisions,
        )

    def _run_claude_code(self, prompt: str) -> Dict[str, Any]:
        """Run Claude Code with the given prompt."""
        cmd = [
            "claude",
            "--print",  # Non-interactive mode
            "--output-format", "json",
            prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max per invocation
                cwd=self.working_dir,
            )

            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"success": True, "output": result.stdout}
            else:
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr,
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Task timeout (1h)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backoff(self, attempt: int) -> None:
        """Exponential backoff between retries."""
        delay = min(
            self.config.backoff_base_seconds * (2 ** attempt),
            self.config.backoff_max_seconds
        )
        self.oversight.log("INFO", f"Backing off for {delay:.1f}s")
        time.sleep(delay)

    def _elapsed_hours(self) -> float:
        """Get elapsed runtime in hours."""
        if not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds() / 3600

    def _checkpoint(self) -> None:
        """Save current state for resume capability."""
        data = CheckpointData(
            timestamp=datetime.now().isoformat(),
            tasks_total=len(self.tasks),
            tasks_completed=len(self.results),
            results=[r.__dict__ for r in self.results],
            state=self.state.value,
        )
        self.oversight.save_checkpoint(data)

    def run(self) -> "MorningReport":
        """
        Run all tasks overnight.

        Returns a MorningReport summarizing what happened.
        """
        self.start_time = datetime.now()
        self.state = LoopState.RUNNING
        self.oversight.log("INFO", f"Starting overnight run with {len(self.tasks)} tasks")
        self.oversight.log("INFO", f"Config: {self.config.max_runtime_hours}h max, "
                          f"{self.config.max_task_retries} retries per task")

        # Initial checkpoint
        self._checkpoint()
        last_checkpoint = time.time()

        try:
            for i, task in enumerate(self.tasks):
                # Check limits before each task
                limit_reason = self._check_limits()
                if limit_reason:
                    self.oversight.log("WARNING", f"Stopping: {limit_reason}")
                    self.state = LoopState.LIMIT_REACHED
                    break

                self.oversight.log("INFO", f"Starting task {i+1}/{len(self.tasks)}: {task[:50]}...")

                # Execute task
                result = self._execute_task(task)
                self.results.append(result)

                if result.success:
                    self.oversight.log("INFO", f"Task {i+1} completed successfully")
                else:
                    self.oversight.log("WARNING", f"Task {i+1} failed: {result.error}")

                # Periodic checkpoint
                if time.time() - last_checkpoint > self.config.checkpoint_interval_minutes * 60:
                    self._checkpoint()
                    last_checkpoint = time.time()

            if self.state == LoopState.RUNNING:
                self.state = LoopState.COMPLETED

        except KeyboardInterrupt:
            self.oversight.log("WARNING", "Interrupted by user")
            self.state = LoopState.INTERRUPTED
        except Exception as e:
            self.oversight.log("ERROR", f"Unexpected error: {e}")
            self.state = LoopState.ERROR
        finally:
            self._checkpoint()

        # Generate morning report
        return self._generate_report()

    def _generate_report(self) -> "MorningReport":
        """Generate a summary report of the overnight run."""
        return MorningReport(
            start_time=self.start_time,
            end_time=datetime.now(),
            total_tasks=len(self.tasks),
            completed_tasks=len([r for r in self.results if r.success]),
            failed_tasks=len([r for r in self.results if not r.success]),
            final_state=self.state,
            results=self.results,
            logs=self.oversight.get_logs(),
        )

    def resume(self) -> "MorningReport":
        """Resume from the last checkpoint."""
        checkpoint = self.oversight.load_checkpoint()
        if not checkpoint:
            raise ValueError("No checkpoint found to resume from")

        self.oversight.log("INFO", f"Resuming from checkpoint: {checkpoint.timestamp}")

        # Restore state
        completed = checkpoint.tasks_completed
        self.tasks = self.tasks[completed:]
        self.state = LoopState(checkpoint.state)

        return self.run()


class StuckError(Exception):
    """Raised when stuck pattern is detected."""
    pass


@dataclass
class MorningReport:
    """Summary report of an overnight run."""
    start_time: Optional[datetime]
    end_time: datetime
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    final_state: LoopState
    results: List[TaskResult]
    logs: List[str]

    @property
    def success_rate(self) -> float:
        """Percentage of tasks that succeeded."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def runtime_hours(self) -> float:
        """Total runtime in hours."""
        if not self.start_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() / 3600

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 60,
            "OVERNIGHT RUN SUMMARY",
            "=" * 60,
            f"Status: {self.final_state.value}",
            f"Runtime: {self.runtime_hours:.1f} hours",
            f"Tasks: {self.completed_tasks}/{self.total_tasks} completed "
            f"({self.success_rate:.0f}%)",
            "",
            "RESULTS:",
        ]

        for i, result in enumerate(self.results):
            status = "✓" if result.success else "✗"
            lines.append(f"  {status} Task {i+1}: "
                        f"{'Success' if result.success else result.error or 'Failed'} "
                        f"({result.duration_seconds:.1f}s, {result.retries} retries)")

        if self.failed_tasks > 0:
            lines.extend([
                "",
                "FAILURES:",
            ])
            for i, result in enumerate(self.results):
                if not result.success:
                    lines.append(f"  Task {i+1}: {result.error}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export report as JSON."""
        return json.dumps({
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat(),
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "runtime_hours": self.runtime_hours,
            "final_state": self.final_state.value,
            "results": [r.__dict__ for r in self.results],
        }, indent=2)
