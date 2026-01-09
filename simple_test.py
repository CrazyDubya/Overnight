#!/usr/bin/env python3
"""Simple test to see if claude CLI triggers."""
import subprocess
import sys
import os

# Set an invalid API key to ensure we get an auth error
os.environ["ANTHROPIC_API_KEY"] = "sk-test-invalid-12345"

print("Testing claude CLI invocation...")
print("=" * 50)

cmd = ["claude", "--print", "--dangerously-skip-permissions", "Say hello"]
print(f"Command: {' '.join(cmd)}")
print("-" * 50)

try:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait up to 10 seconds
    stdout, stderr = proc.communicate(timeout=10)

    print(f"Return code: {proc.returncode}")
    print(f"STDOUT:\n{stdout or '(empty)'}")
    print(f"STDERR:\n{stderr or '(empty)'}")

except subprocess.TimeoutExpired:
    proc.kill()
    stdout, stderr = proc.communicate()
    print("TIMEOUT after 10s")
    print(f"STDOUT before kill:\n{stdout or '(empty)'}")
    print(f"STDERR before kill:\n{stderr or '(empty)'}")

except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")

print("=" * 50)
print("Test complete")
