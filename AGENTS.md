# rokt-workflows - Agent Instructions

Reusable GitHub Actions workflows, composite actions, and a Trunk linter plugin, all consumed by
other ROKT repos. `README.md` has the public surface; `.trunk/trunk.yaml`, `requirements.txt`, and
`.github/workflows/` have the versions, the enabled linters, and what CI does. None of that is
repeated here — a copy drifts and config cannot. This file is only what those files will not tell
you.

## What makes this repo unusual

- **Everything in it is some other repo's CI.** There are no tags and no releases, so `main` is
  the only ref a consumer can track and a merge is a deploy. `validate_actions_versions.py`
  exempts `ROKT/rokt-workflows/` from SHA pinning, so a consumer may legitimately reference
  `@main` and pick your commit up on its next run; others pin a SHA and bump it via dependabot
  (`ROKT/rokt-sdk-flutter` does). Assume both kinds of caller exist.
- **There is no test suite.** No test files, no pytest, and `requirements.txt` is the only
  dependency manifest — no `pyproject.toml`, poetry, uv, or pipenv. `trunk check` is the whole
  automated gate and it is static analysis only, so any behaviour change to the Python has to be
  exercised by hand. Both entry points are plain CLI scripts, so run them against a fixture.

## Commands

- Reproduce the CI lint gate: `trunk check --all` (one linter: `--filter=mypy`). Format:
  `trunk fmt`.
- Exercise either script directly, since nothing else does. The linter takes a file argument; the
  changelog generator reads `INPUT_*` env vars mirroring `actions/generate-changelog/action.yml`
  and needs at least `INPUT_VERSION` and `GITHUB_REPOSITORY`.

### Command traps

1. **A bare `trunk check` checks your diff, not the repo.** On a clean tree it prints
   `No modified files. Nothing to do` and exits 0, which reads as a pass. CI passes
   `check-mode: all` (`.github/workflows/trunk-lint.yml`), so `--all` is what reproduces it.
2. **The venv must be a genuine Python 3.10 venv:**
   `python3.10 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Both
   `.github/workflows/trunk-lint.yml` and `.trunk/trunk.yaml` hardcode
   `.venv/lib/python3.10/site-packages` as the `PYTHONPATH` for mypy, pylint, and pyright. Another
   interpreter puts the packages in a differently named directory and `trunk check --all` then
   reports `Unable to import 'yaml'` (pylint E0401) and `Import "yaml" could not be resolved`
   (pyright). Faking the directory name is not enough — compiled extensions are ABI-tagged. Name
   the interpreter; bare `python` does not exist on macOS.
3. **There are two different mypys.** CI type-checks with the `mypy` Trunk manages, at the version
   in `.trunk/trunk.yaml`; `requirements.txt` pins a different one, so `python3 -m mypy .` is not
   the gate. CI installs `requirements.txt` only so Trunk's checkers can resolve `yaml` and its
   stubs.
4. **mypy has no config file in the repo, so it runs on defaults** — the body of an _unannotated_
   function is not type-checked at all. Green mypy says nothing about code you did not annotate.
5. **Any `trunk` invocation takes over `core.hooksPath`.** `.trunk/trunk.yaml` enables
   `trunk-fmt-pre-commit` and `trunk-check-pre-push`, so the first `trunk` run in a fresh clone
   repoints git at a Trunk-managed hooks directory and pre-commit starts rewriting your files.
   Bypass a single commit with `git -c core.hooksPath=/dev/null commit`; do not disable it in the
   config.

## Gotchas

1. **`validate-actions-versions` cannot see a composite action at all.** `validate_workflow()`
   walks only `workflow["jobs"]`, and a composite action puts its steps under `runs.steps` — so a
   composite action full of unpinned `uses:` exits 0. Independently, the file patterns in
   `rokt-trunk-plugin/linters/validate-actions-versions/plugin.yaml` cover `.github/workflows/`
   and `.github/actions/`, not this repo's top-level `actions/`. Two holes stacked over the
   linter's entire stated purpose: never cite a green run as evidence that an action is pinned.
2. **`generate-changelog` is a silent no-op unless the target file already has an
   `## [Unreleased]` heading.** `_insert_version_section` inserts only after that heading, and
   `_ensure_changelog_exists` writes a skeleton only when the file is missing entirely. Against an
   existing `CHANGELOG.md` without the heading it prints `Updated CHANGELOG.md`, sets the
   `release-notes` output, exits 0 — and leaves the file byte-identical. The `[unreleased]:` link
   line behaves the same way for the comparison links.
3. **Every `git` and `gh` failure inside `generate_changelog.py` degrades silently.** `_run_cmd`
   returns `""` for a non-zero exit or a missing binary, so a shallow checkout has no tags, reads
   as "no previous release tag", and puts all of history in the release notes; an unauthenticated
   `gh` falls back to the raw squash-commit subject instead of the PR title. Callers must check out
   with `fetch-depth: 0`, as `README.md` says. Relatedly, `find_last_tag` requires the whole tag to
   match `^v?\d+\.\d+\.\d+$` after applying the prefix, so any `tag-prefix` other than `v` is
   discarded the same silent way.
4. **Zizmor never blocks.** `.github/workflows/zizmor.yml` sets `continue-on-error: true`
   deliberately, and the workflow is `paths:`-scoped to `.github/workflows/**` and `actions/**`, so
   a change under `rokt-trunk-plugin/` is never scanned at all.
5. **`notify-gchat` fails on every PR raised in this repo.** `oss_pr_opened_notification.yml`
   triggers on `pull_request` as well as `workflow_call`, but `secrets.gchat_webhook` only exists
   on the `workflow_call` path, so a `pull_request` run gets an empty `webhookUrl` and fails. Not
   your change.
6. **Trunk Lint can turn red on `main` with nobody committing.** Semgrep's rules come from its
   registry at run time, not from the version pinned in `.trunk/trunk.yaml`, so a newly published
   rule reddens a file that was green yesterday. `.github/dependabot.yml` is red this way today (a
   missing `cooldown` block) — check whether it still is before assuming your diff caused it.

## Repository etiquette

- Base PRs on `main`. Merges are squash-only and the squash subject is the PR title, so write the
  title as a conventional commit.
- The `Default` ruleset on `main` requires one **code-owner** approval (`.github/CODEOWNERS`) and
  every review thread resolved. It dismisses approvals on push and requires the last push to be
  approved, so finish pushing before asking for review. It also requires an extra approval for
  commits GitHub cannot attribute to a user, so commit with an email tied to your GitHub account.
- That ruleset requires **no status checks**. A red Trunk Lint or `notify-gchat` does not block a
  merge; a missing code-owner approval does.
- Copilot review is a ruleset rule, so it comments on every PR without being asked.
- A caller of `trunk-upgrade.yml` should pass the `token` input a GitHub App token: a PR opened
  with the default `GITHUB_TOKEN` does not trigger the calling repo's workflows.
