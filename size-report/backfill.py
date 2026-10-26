#!/usr/bin/env python3
"""Backfill the size-impact section onto a repository's existing releases.

Usage:
  backfill.py plan    PRODUCT --repo OWNER/NAME
  backfill.py measure PRODUCT --repo OWNER/NAME --results DIR
  backfill.py render  PRODUCT --repo OWNER/NAME --results DIR --out DIR [--method-url URL]
  backfill.py apply   PRODUCT --repo OWNER/NAME --out DIR [--tag TAG ...]

PRODUCT is a key of repos.json; --repo is the repository whose releases carry it.

`plan` lists the releases in scope (the `backfill_major` in repos.json). `measure` runs
<platform>/measure.sh once per package and version, skipping results already in DIR, so it can
be stopped and resumed; each measurement's log is kept beside its result. `render` writes each
release's new body to OUT/<tag>.md for review, without touching GitHub. `apply` publishes the
reviewed files with `gh release edit`; it is the only command that writes anything, and only
for the bodies in OUT.
"""

import argparse
import json
import subprocess  # nosec B404 -- runs gh and the sibling measure scripts with argument lists
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from previous_release import parse, previous
from render_release_size import render
from rows import rows_for
from update_release_body import update

HERE = Path(__file__).resolve().parent


def config(product: str) -> dict:
    """The repos.json entry for product."""
    products = json.loads((HERE / "repos.json").read_text(encoding="utf-8"))
    if product not in products:
        sys.exit(f"{product} is not in repos.json")
    return products[product]


def gh(*args: str) -> str:
    """Run gh and return its stdout."""
    return subprocess.run(  # nosec B603 B607 -- fixed gh invocation, no shell
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def releases(repo: str) -> List[dict]:
    """Every release of repo, as gh reports it."""
    fields = "tagName,isPrerelease,isDraft"
    return json.loads(
        gh("release", "list", "--repo", repo, "--limit", "1000", "--json", fields)
    )


def version_of(tag: str) -> str:
    """The package version a tag names, without any leading v."""
    return tag[1:] if tag.startswith("v") else tag


def major_of(tag: str) -> Optional[int]:
    """Major version of a tag, pre-release or not."""
    parsed = parse(tag.split("-")[0])
    return parsed[0] if parsed else None


def in_scope(args: argparse.Namespace) -> List[Tuple[str, str, Optional[str]]]:
    """(tag, version, previous stable version) for every non-draft release in the backfill major."""
    wanted = config(args.product)["backfill_major"]
    every = releases(args.repo)
    scope = []
    for release in every:
        tag = release["tagName"]
        if release.get("isDraft") or major_of(tag) != wanted:
            continue
        version = version_of(tag)
        # A pre-release compares against the stable release before its own base version.
        scope.append((tag, version, previous(every, version.split("-")[0])))
    return sorted(scope, key=lambda item: item[1])


def command_plan(args: argparse.Namespace) -> None:
    """Print the releases in scope."""
    for tag, version, prior in in_scope(args):
        print(f"{tag}\t{version}\tprevious={prior or '-'}")


def command_measure(args: argparse.Namespace) -> None:
    """Measure every package and version in scope that has no result yet."""
    platform = config(args.product)["platform"]
    results = Path(args.results)
    results.mkdir(parents=True, exist_ok=True)
    scope = in_scope(args)
    versions = sorted({v for _, version, prior in scope for v in (version, prior) if v})
    measure = HERE / platform / "measure.sh"
    for version in versions:
        for package in (
            row.partition("=")[0] for row in rows_for(args.product, version)
        ):
            target = results / f"{package}-{version}.json"
            # An empty result is a failed or interrupted run: measure it again.
            if target.exists() and target.stat().st_size:
                continue
            print(f"measuring {package} {version}", file=sys.stderr)
            log = results / f"{package}-{version}.log"
            with target.open("w", encoding="utf-8") as out, log.open(
                "w", encoding="utf-8"
            ) as err:
                done = subprocess.run(  # nosec B603 -- the sibling measure script
                    [str(measure), package, version],
                    stdout=out,
                    stderr=err,
                    check=False,
                )
            if done.returncode != 0:
                print(f"  not measured: {package} {version}", file=sys.stderr)


def command_render(args: argparse.Namespace) -> None:
    """Write each release's new body to the review directory."""
    platform = config(args.product)["platform"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for tag, version, prior in in_scope(args):
        rows = rows_for(args.product, version)
        had = (
            {row.partition("=")[0] for row in rows_for(args.product, prior)}
            if prior
            else set()
        )
        section = render(
            argparse.Namespace(
                platform=platform,
                version=version,
                previous=prior,
                results_dir=args.results,
                row=rows,
                method_url=args.method_url,
                new=[
                    row.partition("=")[0]
                    for row in rows
                    if row.partition("=")[0] not in had
                ],
            )
        )
        body = gh(
            "release",
            "view",
            tag,
            "--repo",
            args.repo,
            "--json",
            "body",
            "--jq",
            ".body",
        )
        (out / f"{tag}.md").write_text(update(body, section), encoding="utf-8")
        print(f"rendered {out / f'{tag}.md'}")


def command_apply(args: argparse.Namespace) -> None:
    """Publish reviewed bodies with gh release edit."""
    out = Path(args.out)
    tags = args.tag or [path.stem for path in sorted(out.glob("*.md"))]
    for tag in tags:
        gh(
            "release",
            "edit",
            tag,
            "--repo",
            args.repo,
            "--notes-file",
            str(out / f"{tag}.md"),
        )
        print(f"updated {args.repo} {tag}")


def main() -> int:
    """Dispatch to a subcommand."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "measure", "render", "apply"):
        command = commands.add_parser(name)
        command.add_argument("product")
        command.add_argument("--repo", required=True)
        if name in ("measure", "render"):
            command.add_argument("--results", required=True)
        if name in ("render", "apply"):
            command.add_argument("--out", required=True)
        if name == "render":
            command.add_argument("--method-url")
        if name == "apply":
            command.add_argument("--tag", action="append")
    args = parser.parse_args()
    {
        "plan": command_plan,
        "measure": command_measure,
        "render": command_render,
        "apply": command_apply,
    }[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
