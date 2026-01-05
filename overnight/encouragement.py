"""
Overnight mode prompts and "encouragement" system.

This module provides the psychological/prompt-engineering framework
for enabling Claude Code to operate autonomously overnight:

1. Clear expectations about autonomous operation
2. Permission frameworks for decision-making
3. Recovery-oriented mindset guidance
4. Morning report mentality

The key insight: Claude Code normally expects human oversight and
confirmation. For overnight operation, we need to explicitly signal
that autonomous decision-making is expected and encouraged.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class RiskAssessment:
    """Assessment of an action's risk level."""
    level: str  # "low", "medium", "high", "critical"
    factors: List[str]
    recommendation: str  # "proceed", "proceed_with_logging", "skip", "abort"


class OvernightPrompts:
    """
    Generates prompts that prime Claude Code for overnight operation.

    The prompts establish:
    - That no human monitoring is expected
    - Permission to make reasonable autonomous decisions
    - Emphasis on documentation and logging
    - Recovery-oriented thinking
    - Clear risk assessment frameworks
    """

    # Core overnight mode preamble
    OVERNIGHT_PREAMBLE = """
## OVERNIGHT OPERATION MODE

You are running in **overnight mode**. This means:

1. **No human is monitoring** - You are expected to work autonomously
2. **Make reasonable decisions** - Don't wait for confirmation on routine matters
3. **Document everything** - Leave clear logs for morning review
4. **Prioritize safety** - When uncertain, choose the conservative path
5. **Recovery mindset** - If stuck, try alternatives before giving up

### Decision Framework

For any decision point:
- **Low risk** (formatting, comments, tests): Proceed autonomously
- **Medium risk** (refactoring, new files): Proceed with detailed logging
- **High risk** (architecture, external calls): Log reasoning, proceed carefully
- **Critical risk** (data loss, security): Skip and document for human review

### If You Get Stuck

1. Try an alternative approach (up to 3 times)
2. Simplify the problem
3. Skip and move to next task
4. Document what you tried for morning review

### Morning Report Mindset

Imagine explaining your night's work to the human tomorrow:
- What did you accomplish?
- What decisions did you make and why?
- What needs human attention?
- What would you do differently?
"""

    # Risk-calibrated decision guidance
    RISK_GUIDANCE = {
        1: """
### Risk Tolerance: VERY CONSERVATIVE (Level 1)

- Only make changes you are 100% confident about
- Skip anything that requires judgment calls
- Prefer doing less but doing it perfectly
- Document extensively, ask implicitly via logs
""",
        2: """
### Risk Tolerance: CONSERVATIVE (Level 2)

- Make confident changes autonomously
- For uncertain changes, try the safest option first
- Skip if multiple attempts fail
- Good documentation is required
""",
        3: """
### Risk Tolerance: BALANCED (Level 3)

- Proceed with reasonable confidence
- Try alternative approaches when blocked
- Make judgment calls but document reasoning
- Balance throughput with safety
""",
        4: """
### Risk Tolerance: PROGRESSIVE (Level 4)

- Favor making progress over perfect safety
- Try creative solutions to blockers
- Document decisions but don't over-document
- Accept some risk for better throughput
""",
        5: """
### Risk Tolerance: AGGRESSIVE (Level 5)

- Prioritize completing tasks
- Try bold approaches to problems
- Minimal documentation overhead
- High tolerance for experimental changes
""",
    }

    def __init__(self, risk_tolerance: int = 2):
        """
        Initialize with a risk tolerance level (1-5).

        1 = Very conservative (safest)
        5 = Aggressive (most autonomous)
        """
        self.risk_tolerance = max(1, min(5, risk_tolerance))

    def get_base_prompt(self) -> str:
        """Get the base overnight mode prompt."""
        return self.OVERNIGHT_PREAMBLE + self.RISK_GUIDANCE[self.risk_tolerance]

    def wrap_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Wrap a task with overnight mode context.

        Args:
            task: The task to perform
            context: Optional context (retry count, elapsed time, etc.)

        Returns:
            Prompt with overnight mode preamble and context
        """
        context = context or {}

        # Build context section
        context_lines = []
        if context.get("retry_count", 0) > 0:
            context_lines.append(
                f"Note: This is retry #{context['retry_count']}. "
                "Try a different approach than before."
            )
        if context.get("elapsed_hours", 0) > 0:
            context_lines.append(
                f"Runtime: {context['elapsed_hours']:.1f} hours elapsed"
            )
        if context.get("tasks_completed", 0) > 0:
            context_lines.append(
                f"Progress: {context['tasks_completed']} tasks completed, "
                f"{context.get('tasks_remaining', '?')} remaining"
            )

        context_section = ""
        if context_lines:
            context_section = "\n### Current Context\n" + "\n".join(context_lines) + "\n"

        return f"""
{self.get_base_prompt()}
{context_section}
## YOUR TASK

{task}

---
Remember: You are in overnight mode. Make decisions, document them, and keep moving.
If truly stuck after multiple attempts, skip and continue.
"""

    def get_recovery_suggestion(self, error: str) -> str:
        """Get a suggestion for recovering from an error."""
        # Analyze error type and suggest recovery
        error_lower = error.lower()

        if "timeout" in error_lower:
            return "Break task into smaller chunks that complete faster"
        elif "permission" in error_lower or "access" in error_lower:
            return "Skip files requiring elevated permissions, document for human review"
        elif "not found" in error_lower:
            return "Search for alternative file locations or skip if non-critical"
        elif "syntax" in error_lower or "parse" in error_lower:
            return "Review recent changes, consider reverting last modification"
        elif "test" in error_lower and "fail" in error_lower:
            return "Analyze test output, fix obvious issues, skip flaky tests"
        elif "network" in error_lower or "connection" in error_lower:
            return "Wait and retry with backoff, skip external dependencies if persistent"
        elif "memory" in error_lower or "resource" in error_lower:
            return "Process in smaller batches, skip memory-intensive operations"
        else:
            return "Try alternative approach, simplify scope, or skip to next task"

    def assess_risk(self, action: str, context: Dict[str, Any]) -> RiskAssessment:
        """
        Assess the risk of a proposed action.

        Returns a RiskAssessment with level and recommendation.
        """
        action_lower = action.lower()

        # Critical risk indicators
        critical_patterns = [
            "delete", "drop", "truncate", "rm -rf",
            "production", "credential", "secret", "password",
            "deploy", "publish", "release",
        ]

        # High risk indicators
        high_patterns = [
            "database", "migration", "schema",
            "api", "endpoint", "external",
            "auth", "security", "permission",
            "config", "environment",
        ]

        # Medium risk indicators
        medium_patterns = [
            "refactor", "rename", "move", "restructure",
            "new file", "new module", "new class",
            "dependency", "package", "install",
        ]

        # Check patterns
        factors = []

        for pattern in critical_patterns:
            if pattern in action_lower:
                factors.append(f"Critical pattern: {pattern}")
                return RiskAssessment(
                    level="critical",
                    factors=factors,
                    recommendation="abort"
                )

        for pattern in high_patterns:
            if pattern in action_lower:
                factors.append(f"High-risk pattern: {pattern}")

        for pattern in medium_patterns:
            if pattern in action_lower:
                factors.append(f"Medium-risk pattern: {pattern}")

        # Determine level and recommendation
        if len([f for f in factors if "High-risk" in f]) > 0:
            if self.risk_tolerance >= 3:
                return RiskAssessment(
                    level="high",
                    factors=factors,
                    recommendation="proceed_with_logging"
                )
            else:
                return RiskAssessment(
                    level="high",
                    factors=factors,
                    recommendation="skip"
                )

        if len([f for f in factors if "Medium-risk" in f]) > 0:
            return RiskAssessment(
                level="medium",
                factors=factors,
                recommendation="proceed_with_logging"
            )

        return RiskAssessment(
            level="low",
            factors=["No risk patterns detected"],
            recommendation="proceed"
        )

    def format_decision_log(
        self,
        decision: str,
        reasoning: str,
        risk_level: str,
        outcome: Optional[str] = None
    ) -> str:
        """Format a decision for logging."""
        lines = [
            f"DECISION: {decision}",
            f"RISK: {risk_level}",
            f"REASONING: {reasoning}",
        ]
        if outcome:
            lines.append(f"OUTCOME: {outcome}")
        return " | ".join(lines)


class TaskDecomposer:
    """
    Helps break down complex tasks into smaller, safer subtasks.

    Used when:
    - A task is too risky to execute as-is
    - A task keeps failing and needs simplification
    - Better progress tracking is needed
    """

    def decompose(self, task: str) -> List[str]:
        """
        Decompose a complex task into subtasks.

        This is a heuristic-based decomposition.
        """
        subtasks = []

        # Common decomposition patterns
        task_lower = task.lower()

        if "and" in task_lower:
            # Split on "and"
            parts = task.split(" and ")
            if len(parts) > 1:
                return [p.strip() for p in parts if p.strip()]

        if "then" in task_lower:
            # Split on "then"
            parts = task.split(" then ")
            if len(parts) > 1:
                return [p.strip() for p in parts if p.strip()]

        # Pattern-based decomposition
        if "fix all" in task_lower or "update all" in task_lower:
            subtasks.append(f"List all items to fix/update for: {task}")
            subtasks.append(f"Fix/update items one at a time for: {task}")
            subtasks.append(f"Verify all fixes for: {task}")
            return subtasks

        if "refactor" in task_lower:
            subtasks.append(f"Analyze current structure for: {task}")
            subtasks.append(f"Plan refactoring approach for: {task}")
            subtasks.append(f"Implement refactoring for: {task}")
            subtasks.append(f"Verify refactoring for: {task}")
            return subtasks

        if "test" in task_lower and "fix" in task_lower:
            subtasks.append("Run tests and identify failures")
            subtasks.append("Analyze each failing test")
            subtasks.append("Fix failures one at a time")
            subtasks.append("Verify all tests pass")
            return subtasks

        # Default: return original task
        return [task]


class MorningReportGenerator:
    """
    Generates human-friendly morning reports.

    The report should answer:
    - What was accomplished?
    - What decisions were made?
    - What needs attention?
    - What's the state of the codebase?
    """

    def generate(
        self,
        completed_tasks: List[str],
        failed_tasks: List[str],
        decisions: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> str:
        """Generate a morning report."""
        lines = [
            "# ☀️ Overnight Run Report",
            "",
            "## Summary",
            f"- **Tasks Completed**: {len(completed_tasks)}",
            f"- **Tasks Failed**: {len(failed_tasks)}",
            f"- **Runtime**: {metrics.get('runtime_hours', 0):.1f} hours",
            "",
        ]

        if completed_tasks:
            lines.extend([
                "## ✅ Completed",
                "",
            ])
            for task in completed_tasks:
                lines.append(f"- {task}")
            lines.append("")

        if failed_tasks:
            lines.extend([
                "## ❌ Failed (Needs Attention)",
                "",
            ])
            for task in failed_tasks:
                lines.append(f"- {task}")
            lines.append("")

        if decisions:
            lines.extend([
                "## 🤔 Decisions Made",
                "",
            ])
            for d in decisions[:10]:  # Top 10 decisions
                lines.append(f"- **{d.get('type', 'decision')}**: {d.get('context', '')[:50]}")
                lines.append(f"  - Reasoning: {d.get('reasoning', '')[:80]}")
            lines.append("")

        lines.extend([
            "## 📋 Recommended Actions",
            "",
        ])
        if failed_tasks:
            lines.append("1. Review failed tasks and determine if manual intervention needed")
        if len([d for d in decisions if d.get('risk_level') == 'high']) > 0:
            lines.append("2. Review high-risk decisions made during the night")
        lines.append("3. Run full test suite to verify overnight changes")
        lines.append("4. Review git diff for all changes made")

        return "\n".join(lines)
