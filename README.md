# Overnight

A harness to run Claude Code autonomously overnight with proper oversight, loop detection, and progress tracking.

## The Problem

Claude Code normally operates with human oversight - expecting confirmation for important decisions, waiting for input when stuck, and relying on real-time feedback. This works great for interactive sessions, but what about overnight tasks where no one is monitoring?

## The Solution

Overnight provides infrastructure to run Claude Code autonomously by:

1. **Setting Clear Expectations** - Explicit prompts that communicate "overnight mode" to Claude
2. **Providing Guardrails** - Time limits, iteration caps, and risk assessment
3. **Detecting Stuck States** - Pattern recognition for loops and repeated errors
4. **Enabling Recovery** - Automatic retry with backoff and alternative approaches
5. **Maintaining Oversight** - Detailed logging and checkpoint/resume capability
6. **Generating Reports** - Morning summaries of what happened overnight

## Prerequisites

**Important**: This harness requires Claude Code CLI to be authenticated before use.

```bash
# First, authenticate Claude Code interactively
claude

# Once authenticated, you can run overnight tasks
overnight run "Your task here"
```

The harness spawns Claude Code processes which need access to your authentication. This works with:
- **Claude Pro/Team subscriptions** (OAuth authentication)
- **API keys** (set `ANTHROPIC_API_KEY` environment variable)

### Future: Claude SDK Integration

For production use with full capabilities (tool use, file operations, bash, cost controls), we plan to integrate with the Claude Agent SDK when available. The current CLI-based approach is a stepping stone.

## Installation

```bash
pip install overnight
```

Or from source:

```bash
git clone https://github.com/CrazyDubya/Overnight.git
cd Overnight
pip install -e .
```

## Quick Start

```bash
# First: ensure Claude Code is authenticated
claude  # Interactive login if needed

# Initialize configuration
overnight init

# Run a single task overnight
overnight run "Fix all TypeScript errors in src/"

# Run multiple tasks
overnight run "Fix type errors" "Run tests and fix failures" "Update documentation"

# Check status
overnight status

# Generate report
overnight report
```

## Configuration

Create `overnight.json`:

```json
{
  "max_runtime_hours": 8.0,
  "max_idle_minutes": 30.0,
  "max_task_retries": 3,
  "max_total_iterations": 1000,
  "stuck_threshold": 3,
  "risk_tolerance": 2,
  "checkpoint_interval_minutes": 5.0,
  "protected_paths": [".env", "secrets/", "production/"]
}
```

### Risk Tolerance Levels

| Level | Description | Use When |
|-------|-------------|----------|
| 1 | Very Conservative | Critical systems, you want maximum safety |
| 2 | Conservative (default) | Production code, prefer safety over speed |
| 3 | Balanced | Development code, reasonable autonomy |
| 4 | Progressive | Experimental code, favor progress |
| 5 | Aggressive | Throwaway/spike code, maximum autonomy |

## How It Works

### 1. Overnight Mode Prompts

The harness wraps your tasks with special prompts that prime Claude for autonomous operation:

```
## OVERNIGHT OPERATION MODE

You are running in overnight mode. This means:

1. No human is monitoring - You are expected to work autonomously
2. Make reasonable decisions - Don't wait for confirmation on routine matters
3. Document everything - Leave clear logs for morning review
4. Prioritize safety - When uncertain, choose the conservative path
5. Recovery mindset - If stuck, try alternatives before giving up
```

### 2. Stuck Detection

The system monitors for patterns indicating Claude is stuck:

- **Repeated identical outputs** - Same response 3+ times
- **Repeated errors** - Same error message appearing repeatedly
- **Known stuck patterns** - "rate limit exceeded", "infinite loop", etc.
- **File churn** - Same file modified repeatedly without progress

### 3. Recovery Strategies

When stuck, the system attempts recovery:

1. **Clear context** - Reset accumulated state and retry
2. **Simplify task** - Break into smaller subtasks
3. **Alternative approach** - Try a different method
4. **Skip and continue** - Move to next task, document for human review

### 4. Decision Framework

Claude is guided to assess risk before acting:

| Risk Level | Action | Documentation |
|------------|--------|---------------|
| Low | Proceed autonomously | Minimal logging |
| Medium | Proceed | Detailed logging |
| High | Proceed carefully | Log reasoning extensively |
| Critical | Skip | Flag for human review |

### 5. Morning Reports

After the overnight run, you get a comprehensive report:

```
==============================================
OVERNIGHT RUN SUMMARY
==============================================
Status: completed
Runtime: 6.2 hours
Tasks: 8/10 completed (80%)

RESULTS:
  ✓ Task 1: Success (45.2s, 0 retries)
  ✓ Task 2: Success (123.4s, 1 retries)
  ✗ Task 3: Max retries exceeded (0.0s, 3 retries)
  ...

FAILURES:
  Task 3: Permission denied accessing /etc/config
  Task 7: Test suite timed out after 1 hour
==============================================
```

## Architecture

```
overnight/
├── __init__.py        # Package exports
├── harness.py         # Main orchestrator
├── oversight.py       # Logging, checkpointing, metrics
├── loops.py           # Execution loops, stuck detection
├── encouragement.py   # Overnight mode prompts
└── cli.py             # Command-line interface
```

### Key Components

**OvernightHarness** - The main orchestrator that:
- Manages task queue
- Enforces limits and guardrails
- Coordinates recovery
- Generates reports

**OversightManager** - Provides:
- Structured logging
- Checkpoint/resume capability
- Decision audit trail
- Metrics collection

**StuckDetector** - Monitors for:
- Repeated outputs
- Error patterns
- Known stuck indicators
- File modification churn

**OvernightPrompts** - Generates:
- Overnight mode preamble
- Risk-calibrated guidance
- Recovery suggestions
- Decision frameworks

## API Usage

```python
from overnight import OvernightHarness, OvernightConfig

# Configure
config = OvernightConfig(
    max_runtime_hours=6,
    risk_tolerance=2,
)

# Create harness
harness = OvernightHarness(config=config)

# Add tasks
harness.add_task("Fix all TypeScript errors")
harness.add_task("Run test suite and fix failures")
harness.add_task("Update API documentation")

# Run overnight
report = harness.run()

# Review results
print(report.summary())
print(f"Success rate: {report.success_rate}%")

# Export detailed report
with open("overnight_report.json", "w") as f:
    f.write(report.to_json())
```

### Resume from Checkpoint

```python
# If interrupted, resume from last checkpoint
report = harness.resume()
```

## Best Practices

### Task Design

1. **Be specific** - "Fix TypeScript errors in src/api/" not "Fix code"
2. **Include verification** - "Run tests after fixing"
3. **Set scope boundaries** - "Only modify files in src/"
4. **Provide context** - "The auth system uses JWT tokens"

### Risk Management

1. Start with low risk tolerance until you trust the setup
2. Use `protected_paths` for sensitive files
3. Review overnight commits before pushing
4. Run in a branch, not main

### Monitoring

1. Check `overnight status` periodically if curious
2. Set up notifications for completion (coming soon)
3. Review morning reports thoroughly

## Conceptual Framework: Branching Exploration

The design of Overnight followed a branching exploration approach:

```
Branch 1: What does "overnight" require?
├─ No monitoring expected
├─ Extended runtime
├─ Potential for getting stuck
└─ Morning visibility

Branch 2: Oversight Mechanisms
├─ Path 2a: Progress Tracking ──► logging, checkpoints, metrics
├─ Path 2b: Guardrails ──► limits, boundaries, rollback
└─ Path 2c: Decision Framework ──► risk assessment, autonomous choices

Branch 3: Loop Structures
├─ Path 3a: Task Execution ──► retry logic, backoff
└─ Path 3b: Self-Monitoring ──► stuck detection, recovery

Branch 4: "Encouragement"
├─ Clear expectations
├─ Permission framework
├─ Recovery mindset
└─ Morning report mentality
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
