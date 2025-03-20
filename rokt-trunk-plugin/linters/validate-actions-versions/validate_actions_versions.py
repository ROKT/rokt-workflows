#!/usr/bin/env python3
"""Ensures GitHub Actions in workflow files are pinned to commit SHAs."""

import re
import sys
from typing import Any, Dict, List

import yaml


def load_workflow_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a GitHub Actions workflow file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        print(f"Error loading workflow file: {e}")
        sys.exit(1)


def validate_action_version(uses: str) -> bool:
    """
    Validate that a GitHub Action is pinned to a specific commit SHA.
    Returns True if valid, False otherwise.
    """
    # Skip local actions (they start with .)
    if uses.startswith("."):
        return True

    # Skip actions from ROKT/rokt-workflows
    if uses.startswith("ROKT/rokt-workflows/"):
        return True

    # Check if it's a GitHub action (contains @)
    if "@" not in uses:
        return False

    # Split into action and version
    _, version = uses.rsplit("@", 1)

    # Check if version is a commit SHA (40 character hex string)
    return bool(re.match(r"^[0-9a-f]{40}$", version))


def find_actions_in_steps(steps: List[Dict[str, Any]]) -> List[str]:
    """Extract all 'uses' fields from steps."""
    return [step["uses"] for step in steps if "uses" in step]


def validate_workflow(workflow: Dict[str, Any]) -> bool:
    """Validate all actions in a workflow file."""
    is_valid = True

    # Check jobs
    for job_name, job in workflow.get("jobs", {}).items():
        # Check if job directly uses a reusable workflow
        if "uses" in job:
            if not validate_action_version(job["uses"]):
                print(
                    f"Error: Job '{job_name}' uses workflow '{job['uses']}' "
                    "which is not pinned to a commit SHA"
                )
                is_valid = False
            continue

        # Check steps in job if present
        steps = job.get("steps", [])
        actions = find_actions_in_steps(steps)

        for action_uses in actions:
            if not validate_action_version(action_uses):
                print(f"Error: Action '{action_uses}' is not pinned to a commit SHA")
                is_valid = False

    return is_valid


def main() -> None:
    """Main entry point for the script."""
    if len(sys.argv) != 2:
        print("Usage: validate_action_versions.py <workflow-file-path>")
        sys.exit(1)

    workflow_path = sys.argv[1]
    workflow = load_workflow_file(workflow_path)

    if validate_workflow(workflow):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
