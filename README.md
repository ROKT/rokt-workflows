# Rokt workflows

This repository hosts Rokt's reusable GitHub workflows that we share across our projects for CI builds.  
It also hosts a [Trunk Plugin](https://docs.trunk.io/cli/configuration/plugins) and associated custom linters.

## Usage

### Workflows

In a child repository, you can reference the shared reusable workflow like this:

```yaml
job-name:
  name: "PR Notification"
  uses: ROKT/rokt-workflows/.github/workflows/oss_pr_opened_notification.yml@main
  secrets:
    gchat_webhook: ${{ secrets.YOUR_SECRET }}
```

[Full Github documentation](https://docs.github.com/en/actions/sharing-automations/reusing-workflows).

### Composite Actions

#### Generate Changelog

Auto-generates a [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) section from git history.
Extracts PR numbers from squash-merge commits, fetches actual PR titles via the GitHub CLI,
categorises them by conventional-commit prefix (`feat:` -> Added, `fix:` -> Fixed, etc.),
updates `CHANGELOG.md` in-place, and outputs the release-notes markdown.

```yaml
- name: Generate changelog from git history
  id: changelog
  uses: ROKT/rokt-workflows/actions/generate-changelog@main
  with:
    version: "4.17.0"
```

The calling workflow must check out the repository with `fetch-depth: 0` so that full git
history and tags are available.

| Input            | Required | Default        | Description                                                                  |
| ---------------- | -------- | -------------- | ---------------------------------------------------------------------------- |
| `version`        | yes      |                | New version number (e.g., `4.17.0`)                                          |
| `repo-url`       | no       | Current repo   | GitHub repository URL for comparison links                                   |
| `tag-prefix`     | no       | Auto-detect    | Tag prefix (e.g., `v`). Leave empty to auto-detect both `v4.x` and `4.x`     |
| `changelog-path` | no       | `CHANGELOG.md` | Path to the changelog file                                                   |
| `exclude-types`  | no       |                | Comma-separated conventional-commit types to exclude (e.g., `chore,ci,test`) |

| Output          | Description                             |
| --------------- | --------------------------------------- |
| `release-notes` | Generated changelog section as markdown |

### Trunk Plugin

You can add the plugin to another repository by running:  
`trunk plugins add https://github.com/ROKT/rokt-workflows <ref> --id=rokt-trunk-plugin`

You should then be able to add any custom linter defined in [rokt-trunk-plugin/linters](rokt-trunk-plugin/linters), e.g.:

`trunk check enable validate-actions-versions`
