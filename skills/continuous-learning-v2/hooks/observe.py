#!/usr/bin/env python3
"""
Continuous Learning v2 - Observation Hook

Captures tool use events for pattern analysis.
Claude Code passes hook data via stdin as JSON.

Usage:
    python observe.py pre    # For PreToolUse hook
    python observe.py post   # For PostToolUse hook

Hook config (in ~/.claude/settings.json):
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{ "type": "command", "command": "python ~/.claude/skills/continuous-learning-v2/hooks/observe.py pre" }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{ "type": "command", "command": "python ~/.claude/skills/continuous-learning-v2/hooks/observe.py post" }]
    }]
  }
}
"""

import json
import sys
import os
from datetime import datetime
import signal
from pathlib import Path

def get_config_dir():
    """Get the configuration directory path."""
    home = Path.home()
    config_dir = home / ".claude" / "homunculus"
    return config_dir

def ensure_dir_exists(path):
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)

def parse_json_input():
    """Parse JSON input from stdin."""
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return None

        data = json.loads(input_data)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return None

def truncate_string(s, max_length=5000):
    """Truncate string to maximum length."""
    if s is None:
        return None
    s_str = str(s)
    return s_str[:max_length]

def archive_if_too_large(observations_file, max_size_mb=10):
    """Archive observations file if it exceeds max size."""
    if not observations_file.exists():
        return

    try:
        file_size_mb = observations_file.stat().st_size / (1024 * 1024)
        if file_size_mb >= max_size_mb:
            config_dir = observations_file.parent
            archive_dir = config_dir / "observations.archive"
            ensure_dir_exists(archive_dir)

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            archive_file = archive_dir / f"observations-{timestamp}.jsonl"
            observations_file.rename(archive_file)
    except Exception as e:
        print(f"Error archiving file: {e}", file=sys.stderr)

def write_observation(observation, observations_file):
    """Write observation to file."""
    try:
        with open(observations_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(observation) + '\n')
    except Exception as e:
        print(f"Error writing observation: {e}", file=sys.stderr)

def signal_observer(config_dir):
    """Signal observer process if running."""
    try:
        pid_file = config_dir / ".observer.pid"
        if pid_file.exists():
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                # Send SIGUSR1 signal
                os.kill(pid, signal.SIGUSR1)
            except ProcessLookupError:
                # Process doesn't exist, remove pid file
                pid_file.unlink(missing_ok=True)
    except Exception:
        # Ignore errors in signaling
        pass

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python observe.py <pre|post>", file=sys.stderr)
        sys.exit(1)

    hook_type = sys.argv[1].lower()
    if hook_type not in ['pre', 'post']:
        print("Usage: python observe.py <pre|post>", file=sys.stderr)
        sys.exit(1)

    # Get config directory
    config_dir = get_config_dir()
    observations_file = config_dir / "observations.jsonl"

    # Check if disabled
    if (config_dir / "disabled").exists():
        sys.exit(0)

    # Ensure directory exists
    ensure_dir_exists(config_dir)

    # Parse input
    input_data = parse_json_input()
    if input_data is None:
        sys.exit(0)

    # Extract fields
    try:
        tool_name = input_data.get('tool_name') or input_data.get('tool', 'unknown')
        tool_input = input_data.get('tool_input') or input_data.get('input', {})
        tool_output = input_data.get('tool_output') or input_data.get('output', '')
        session_id = input_data.get('session_id', 'unknown')

        # Truncate large inputs/outputs
        tool_input_str = truncate_string(tool_input)
        tool_output_str = truncate_string(tool_output)

        # Determine event type
        event = 'tool_start' if hook_type == 'pre' else 'tool_complete'

        # Build observation
        from datetime import timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        observation = {
            'timestamp': timestamp,
            'event': event,
            'tool': tool_name,
            'session': session_id
        }

        if event == 'tool_start' and tool_input_str:
            observation['input'] = tool_input_str
        elif event == 'tool_complete' and tool_output_str:
            observation['output'] = tool_output_str

        # Archive if file too large
        archive_if_too_large(observations_file)

        # Write observation
        write_observation(observation, observations_file)

        # Signal observer if running
        signal_observer(config_dir)

    except Exception as e:
        print(f"Error processing input: {e}", file=sys.stderr)
        sys.exit(0)

    sys.exit(0)

if __name__ == '__main__':
    main()
