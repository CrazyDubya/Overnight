#!/usr/bin/env python3
"""
Quick test script to verify the overnight harness triggers Claude Code.
Expected: Will fail on auth, but demonstrates the integration works.
"""

import subprocess
import sys

def test_direct_claude_call():
    """Test calling claude directly."""
    print("=" * 60)
    print("TEST 1: Direct Claude Code call")
    print("=" * 60)

    cmd = [
        "claude",
        "--print",
        "--output-format", "text",
        "Say hello",
    ]

    print(f"Running: {' '.join(cmd)}")
    print("-" * 40)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"Return code: {result.returncode}")
        print(f"stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
        print(f"stderr: {result.stderr[:500] if result.stderr else '(empty)'}")
    except subprocess.TimeoutExpired:
        print("Timeout - claude is waiting for something")
    except Exception as e:
        print(f"Exception: {e}")

    print()

def test_harness_integration():
    """Test the harness integration."""
    print("=" * 60)
    print("TEST 2: Overnight harness integration")
    print("=" * 60)

    from overnight.harness import OvernightHarness, OvernightConfig
    from overnight.encouragement import OvernightPrompts

    # Show what prompt would be sent
    prompts = OvernightPrompts(risk_tolerance=2)
    wrapped = prompts.wrap_task("Say hello", context={"retry_count": 0})

    print("Wrapped prompt (truncated):")
    print("-" * 40)
    print(wrapped[:800])
    print("...")
    print("-" * 40)

    # Create harness with short timeout
    config = OvernightConfig(
        max_runtime_hours=0.01,  # 36 seconds
        max_task_retries=1,
    )

    harness = OvernightHarness(config=config)
    harness.add_task("Say hello")

    print("\nRunning harness (will timeout quickly)...")
    print("-" * 40)

    report = harness.run()

    print("\nReport:")
    print(report.summary())

if __name__ == "__main__":
    test_direct_claude_call()
    test_harness_integration()
