#!/usr/bin/env python3
"""Test resume functionality with simulated interruption."""
import json
from pathlib import Path
from datetime import datetime

# Create a checkpoint that simulates an interrupted run
# 2 tasks completed, 1 remaining
checkpoint = {
    "timestamp": datetime.now().isoformat(),
    "tasks_total": 3,
    "tasks_completed": 2,
    "results": [
        {
            "task_id": "task_0_1234",
            "success": True,
            "output": "Task 1 completed",
            "error": None,
            "duration_seconds": 1.5,
            "retries": 0,
            "decisions_made": []
        },
        {
            "task_id": "task_1_1235",
            "success": True,
            "output": "Task 2 completed",
            "error": None,
            "duration_seconds": 2.0,
            "retries": 0,
            "decisions_made": []
        }
    ],
    "state": "interrupted",
    "tasks": ["Task A", "Task B", "Task C"],  # Full task list
    "decisions": [],
    "metrics": {}
}

# Write checkpoint
checkpoint_dir = Path(".overnight")
checkpoint_dir.mkdir(exist_ok=True)
with open(checkpoint_dir / "latest_checkpoint.json", "w") as f:
    json.dump(checkpoint, f, indent=2)

print("Created simulated interrupted checkpoint:")
print(f"  Total tasks: {checkpoint['tasks_total']}")
print(f"  Completed: {checkpoint['tasks_completed']}")
print(f"  Remaining: {checkpoint['tasks_total'] - checkpoint['tasks_completed']}")
print(f"  Tasks saved: {checkpoint['tasks']}")
print("\nNow run: overnight resume --test-mode")
