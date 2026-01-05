#!/usr/bin/env python3
"""
Overnight CLI - Run Claude Code autonomously overnight.

Usage:
    overnight run [OPTIONS] TASKS...
    overnight resume
    overnight status
    overnight report

Examples:
    # Run a single task overnight
    overnight run "Fix all TypeScript errors"

    # Run multiple tasks
    overnight run "Fix type errors" "Run tests" "Update docs"

    # Run from a task file
    overnight run --file tasks.txt

    # Run with custom config
    overnight run --config overnight.json "Fix bugs"

    # Resume an interrupted run
    overnight resume

    # Check status of running overnight job
    overnight status

    # Generate report from last run
    overnight report
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .harness import OvernightHarness, OvernightConfig


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="overnight",
        description="Run Claude Code autonomously overnight",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run tasks overnight")
    run_parser.add_argument(
        "tasks",
        nargs="*",
        help="Tasks to run (can be multiple)"
    )
    run_parser.add_argument(
        "--file", "-f",
        type=Path,
        help="File containing tasks (one per line)"
    )
    run_parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Configuration file (JSON)"
    )
    run_parser.add_argument(
        "--max-hours",
        type=float,
        default=8.0,
        help="Maximum runtime in hours (default: 8)"
    )
    run_parser.add_argument(
        "--risk-tolerance",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=2,
        help="Risk tolerance 1-5 (1=conservative, 5=aggressive, default: 2)"
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".overnight"),
        help="Directory for logs and checkpoints"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing"
    )
    run_parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run with mock Claude responses (for testing the harness)"
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per task in seconds (default: 3600)"
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted run")
    resume_parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path(".overnight"),
        help="Directory containing checkpoint"
    )
    resume_parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run with mock Claude responses (for testing)"
    )
    resume_parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per task in seconds (default: 3600)"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Check overnight run status")
    status_parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path(".overnight"),
        help="Directory containing checkpoint"
    )

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report from last run")
    report_parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path(".overnight"),
        help="Directory containing checkpoint"
    )
    report_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)"
    )
    report_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file (default: stdout)"
    )

    # Init command (create default config)
    init_parser = subparsers.add_parser("init", help="Create default configuration")
    init_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("overnight.json"),
        help="Output config file (default: overnight.json)"
    )

    return parser


def load_tasks_from_file(path: Path) -> List[str]:
    """Load tasks from a file (one per line)."""
    tasks = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tasks.append(line)
    return tasks


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the run command."""
    # Collect tasks
    tasks = list(args.tasks) if args.tasks else []
    if args.file:
        tasks.extend(load_tasks_from_file(args.file))

    if not tasks:
        print("Error: No tasks specified. Use positional arguments or --file.", file=sys.stderr)
        return 1

    # Load or create config
    if args.config:
        config = OvernightConfig.from_file(args.config)
    else:
        config = OvernightConfig(
            max_runtime_hours=args.max_hours,
            risk_tolerance=args.risk_tolerance,
            checkpoint_dir=str(args.output_dir),
            task_timeout_seconds=args.timeout,
            test_mode=args.test_mode,
        )

    # Dry run mode
    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Config:")
        print(f"  Max runtime: {config.max_runtime_hours} hours")
        print(f"  Risk tolerance: {config.risk_tolerance}")
        print(f"  Max retries: {config.max_task_retries}")
        print(f"  Task timeout: {config.task_timeout_seconds}s")
        print(f"  Test mode: {config.test_mode}")
        print(f"\nTasks ({len(tasks)}):")
        for i, task in enumerate(tasks, 1):
            print(f"  {i}. {task}")
        print("\nNo actions taken (dry run mode)")
        return 0

    # Create and run harness
    harness = OvernightHarness(config=config)
    harness.add_tasks(tasks)

    print(f"Starting overnight run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if config.test_mode:
        print("[TEST MODE - Using mock Claude responses]")
    print(f"Tasks: {len(tasks)}")
    print(f"Max runtime: {config.max_runtime_hours} hours")
    print(f"Risk tolerance: {config.risk_tolerance}")
    print(f"Task timeout: {config.task_timeout_seconds}s")
    print("-" * 40)

    report = harness.run()

    # Print summary
    print("\n" + report.summary())

    # Save report
    report_file = args.output_dir / "report.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        f.write(report.to_json())
    print(f"\nFull report saved to: {report_file}")

    return 0 if report.failed_tasks == 0 else 1


def cmd_resume(args: argparse.Namespace) -> int:
    """Execute the resume command."""
    config = OvernightConfig(
        checkpoint_dir=str(args.checkpoint_dir),
        test_mode=args.test_mode,
        task_timeout_seconds=args.timeout,
    )
    harness = OvernightHarness(config=config)

    if config.test_mode:
        print("[TEST MODE - Using mock Claude responses]")

    try:
        report = harness.resume()
        print(report.summary())
        return 0 if report.failed_tasks == 0 else 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Execute the status command."""
    checkpoint_file = args.checkpoint_dir / "latest_checkpoint.json"

    if not checkpoint_file.exists():
        print("No overnight run in progress or completed.")
        return 0

    with open(checkpoint_file) as f:
        data = json.load(f)

    print("=== Overnight Run Status ===")
    print(f"State: {data.get('state', 'unknown')}")
    print(f"Last checkpoint: {data.get('timestamp', 'unknown')}")
    print(f"Progress: {data.get('tasks_completed', 0)}/{data.get('tasks_total', 0)} tasks")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Execute the report command."""
    report_file = args.checkpoint_dir / "report.json"

    if not report_file.exists():
        print("No report found. Run 'overnight run' first.", file=sys.stderr)
        return 1

    with open(report_file) as f:
        data = json.load(f)

    if args.format == "json":
        output = json.dumps(data, indent=2)
    elif args.format == "markdown":
        output = generate_markdown_report(data)
    else:
        output = generate_text_report(data)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Execute the init command."""
    config = OvernightConfig()
    config.to_file(args.output)
    print(f"Created default configuration: {args.output}")
    print("\nEdit this file to customize your overnight run settings.")
    return 0


def generate_text_report(data: dict) -> str:
    """Generate a text report from JSON data."""
    lines = [
        "=" * 60,
        "OVERNIGHT RUN REPORT",
        "=" * 60,
        f"Start: {data.get('start_time', 'N/A')}",
        f"End: {data.get('end_time', 'N/A')}",
        f"Runtime: {data.get('runtime_hours', 0):.1f} hours",
        f"Status: {data.get('final_state', 'unknown')}",
        "",
        f"Tasks: {data.get('completed_tasks', 0)}/{data.get('total_tasks', 0)} completed "
        f"({data.get('success_rate', 0):.0f}%)",
        "",
        "Results:",
    ]

    for i, result in enumerate(data.get("results", [])):
        status = "OK" if result.get("success") else "FAIL"
        lines.append(f"  [{status}] Task {i+1}: {result.get('error', 'Success')}")

    return "\n".join(lines)


def generate_markdown_report(data: dict) -> str:
    """Generate a markdown report from JSON data."""
    lines = [
        "# Overnight Run Report",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Start | {data.get('start_time', 'N/A')} |",
        f"| End | {data.get('end_time', 'N/A')} |",
        f"| Runtime | {data.get('runtime_hours', 0):.1f} hours |",
        f"| Status | {data.get('final_state', 'unknown')} |",
        f"| Success Rate | {data.get('success_rate', 0):.0f}% |",
        "",
        "## Results",
        "",
    ]

    for i, result in enumerate(data.get("results", [])):
        status = "✅" if result.get("success") else "❌"
        lines.append(f"{status} **Task {i+1}**: {result.get('error', 'Success')}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "resume": cmd_resume,
        "status": cmd_status,
        "report": cmd_report,
        "init": cmd_init,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
