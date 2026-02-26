# rokt-workflows

## Project Overview

This repository hosts Rokt's reusable GitHub Actions workflows shared across projects for CI builds. It also provides a [Trunk Plugin](https://docs.trunk.io/cli/configuration/plugins) with custom linters. Owned by the **SDK Engineering** team (`@ROKT/sdk-engineering`).

## Architecture

The repo has three main components:

1. **Reusable GitHub Actions Workflows** (`.github/workflows/`) — callable workflows that other ROKT repos reference via `uses: ROKT/rokt-workflows/.github/workflows/<workflow>.yml@main`.
2. **Composite Actions** (`actions/`) — reusable action steps that other ROKT repos reference via `uses: ROKT/rokt-workflows/actions/<action>@main`.
3. **Trunk Plugin** (`rokt-trunk-plugin/`) — a custom Trunk linter plugin that other repos can install to enforce coding standards. Currently includes a `validate-actions-versions` linter that ensures all GitHub Actions are pinned to commit SHAs.

```text
rokt-workflows/
  .github/workflows/        # Reusable workflows consumed by other repos
    oss_pr_opened_notification.yml   # Google Chat notification on PR open
    trunk-lint.yml                   # Trunk lint CI check
    trunk-upgrade.yml                # Monthly trunk config upgrade + auto-PR
  actions/                   # Composite actions consumed by other repos
    generate-changelog/              # Auto-generate Keep a Changelog from git history
  rokt-trunk-plugin/         # Trunk plugin consumed by other repos
    linters/
      validate-actions-versions/     # Custom linter (Python)
  plugin.yaml                # Root Trunk plugin manifest
```

## Tech Stack

- **Python 3.10** — custom linter scripts
- **PyYAML 6.0.2** — YAML parsing for linter
- **mypy 1.15.0** — type checking
- **Trunk CLI 1.25.0** — linting orchestration
- **GitHub Actions** — CI/CD platform

## Development Guide

### Prerequisites

- Python 3.10
- [Trunk CLI](https://docs.trunk.io/cli) (v1.22.2+, repo uses v1.25.0)

### Quick Start

```bash
# Clone and set up Python virtual environment
git clone git@github.com:ROKT/rokt-workflows.git
cd rokt-workflows
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Using the Reusable Workflows

Reference a workflow from another repo:

```yaml
job-name:
  name: "PR Notification"
  uses: ROKT/rokt-workflows/.github/workflows/oss_pr_opened_notification.yml@main
  secrets:
    gchat_webhook: ${{ secrets.YOUR_SECRET }}
```

### Using the Trunk Plugin

Add the plugin to another repo:

```bash
trunk plugins add https://github.com/ROKT/rokt-workflows <ref> --id=rokt-trunk-plugin
trunk check enable validate-actions-versions
```

## Build, Test & Lint Commands

| Command                           | Description                          |
| --------------------------------- | ------------------------------------ |
| `trunk check`                     | Run all enabled linters              |
| `trunk fmt`                       | Auto-format files                    |
| `trunk check AGENTS.md CLAUDE.md` | Lint specific files                  |
| `trunk upgrade`                   | Upgrade trunk and linter versions    |
| `python -m mypy .`                | Run type checking (with venv active) |

### Enabled Linters (via Trunk)

actionlint, bandit, black, checkov, codespell, flake8, git-diff-check, gitleaks, isort, kube-linter, markdownlint, mypy, osv-scanner, prettier, pylint, pyright, ruff, semgrep, sourcery, taplo, trivy, trufflehog, validate-actions-versions, yamllint

## CI/CD Pipeline

CI runs on **GitHub Actions** (not Buildkite):

| Workflow                         | Trigger                                       | Description                                                          |
| -------------------------------- | --------------------------------------------- | -------------------------------------------------------------------- |
| `trunk-lint.yml`                 | PR, manual                                    | Runs `trunk check` with Python 3.10 venv; caches pip dependencies    |
| `trunk-upgrade.yml`              | Monthly cron (1st of month), manual, callable | Runs `trunk upgrade`, creates auto-PR if `.trunk/trunk.yaml` changes |
| `oss_pr_opened_notification.yml` | PR opened/reopened, callable                  | Sends Google Chat notification for new/reopened PRs                  |

Dependabot is configured for weekly GitHub Actions dependency updates.

## Project Structure

| Path                                                   | Description                                                           |
| ------------------------------------------------------ | --------------------------------------------------------------------- |
| `.github/workflows/`                                   | Reusable GitHub Actions workflows                                     |
| `.github/CODEOWNERS`                                   | Team ownership (`@ROKT/sdk-engineering`)                              |
| `.github/pull_request_template.md`                     | PR template                                                           |
| `.github/dependabot.yml`                               | Dependabot config for GitHub Actions updates                          |
| `actions/`                                             | Composite GitHub Actions consumed by other repos                      |
| `actions/generate-changelog/`                          | Auto-generate Keep a Changelog section from git history + PR titles   |
| `rokt-trunk-plugin/`                                   | Trunk plugin with custom linters                                      |
| `rokt-trunk-plugin/linters/validate-actions-versions/` | Custom linter ensuring Actions are SHA-pinned                         |
| `.trunk/trunk.yaml`                                    | Trunk CLI and linter configuration                                    |
| `.trunk/configs/`                                      | Linter-specific configs (markdownlint, yamllint, ruff, flake8, isort) |
| `plugin.yaml`                                          | Root-level Trunk plugin manifest                                      |
| `requirements.txt`                                     | Python dependencies (PyYAML, mypy)                                    |

## Maintaining This Document

When making changes to this repository that affect the information documented here
(build commands, dependencies, architecture, deployment configuration, etc.),
please update this document to keep it accurate. This file is the primary reference
for AI coding assistants working in this codebase.
