#!/usr/bin/env python3
"""Measure what one published iOS SDK release adds to an empty SwiftUI app.

Usage: measure_ios.py <package> <version>

Prints one line of JSON on stdout (see ../README.md); everything else goes to stderr. Exits
non-zero and prints nothing when the version cannot be resolved, built or measured plausibly.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 - runs swift, xcodebuild and git with fixed argument lists
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIB = 1024 * 1024
MAX_PIN_ROUNDS = 8
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
# SwiftPM's wording when another package's exact requirement contradicts one of our pins.
PIN_CONFLICT = re.compile(r"and root depends on '([^']+)' ")


@dataclass(frozen=True)
class Companion:
    """A package pinned to the same version as the measured one, because they ship together."""

    url: str
    # Linked directly when the entry point imports it.
    product: str | None = None


@dataclass(frozen=True)
class Spec:
    """How to pull one package id into the app."""

    url: str
    product: str
    tag_prefix: str
    # A package that adds less than this failed to link; reporting it would show a fake saving.
    floor_bytes: int
    companions: tuple[Companion, ...] = field(default_factory=tuple)


MPARTICLE_CORE_URL = "https://github.com/mParticle/mparticle-apple-sdk"
ROKT_SDK_URL = "https://github.com/ROKT/rokt-sdk-ios"

SPECS: dict[str, Spec] = {
    "mparticle-core": Spec(MPARTICLE_CORE_URL, "mParticle-Apple-SDK", "v", 1 * MIB),
    "mparticle-rokt-kit": Spec(
        "https://github.com/mparticle-integrations/mp-apple-integration-rokt",
        "mParticle-Rokt",
        "v",
        4 * MIB,
        (Companion(MPARTICLE_CORE_URL, "mParticle-Apple-SDK"),),
    ),
    "rokt-sdk": Spec(ROKT_SDK_URL, "Rokt-Widget", "", 3 * MIB),
    "rokt-payment-extension": Spec(
        "https://github.com/ROKT/rokt-payment-extension-ios",
        "RoktPaymentExtension",
        "",
        4 * MIB,
        (Companion(ROKT_SDK_URL, "Rokt-Widget"),),
    ),
    "rokt-ux-helper": Spec(
        "https://github.com/ROKT/rokt-ux-helper-ios", "RoktUXHelper", "", 2 * MIB
    ),
}

# An empty SwiftUI app is well under this; anything larger means the baseline links something.
MAX_BASELINE_BYTES = 2 * MIB


class MeasureError(Exception):
    """A measurement that must fail closed."""


def log(message: str) -> None:
    """Write to stderr so stdout stays one line of JSON."""
    print(message, file=sys.stderr)


def run(args: list[str], cwd: Path | None = None) -> str:
    """Run a command, sending its output to stderr unless it is captured for parsing."""
    result = subprocess.run(  # nosec B603 - fixed executables, no shell
        args, cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-4000:] + result.stderr[-4000:])
        raise MeasureError(
            f"{args[0]} {args[1] if len(args) > 1 else ''} failed ({result.returncode})"
        )
    return result.stdout


def identity(url: str) -> str:
    """SwiftPM's package identity: the last path component, lower-cased, without .git."""
    return url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1].lower()


def semver(tag: str) -> tuple[int, int, int] | None:
    """Parse a stable release tag; pre-releases and other refs return None."""
    match = SEMVER.match(tag)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def manifest(spec: Spec | None, version: str, pins: dict[str, str]) -> str:
    """The generated SizeTarget package: the measured package, its companions and date pins."""
    deps: list[str] = []
    target_deps: list[str] = []
    if spec is not None:
        deps.append(f'.package(url: "{spec.url}", exact: "{version}")')
        target_deps.append(
            f'.product(name: "{spec.product}", package: "{identity(spec.url)}")'
        )
        for companion in spec.companions:
            deps.append(f'.package(url: "{companion.url}", exact: "{version}")')
            if companion.product:
                target_deps.append(
                    f'.product(name: "{companion.product}", package: "{identity(companion.url)}")'
                )
    deps += [
        f'.package(url: "{url}", exact: "{pinned}")'
        for url, pinned in sorted(pins.items())
    ]
    return "\n".join(
        [
            "// swift-tools-version:5.9",
            "import PackageDescription",
            "",
            "let package = Package(",
            '    name: "SizeTarget",',
            "    platforms: [.iOS(.v15)],",
            '    products: [.library(name: "SizeTarget", targets: ["SizeTarget"])],',
            "    dependencies: [",
            *[f"        {dep}," for dep in deps],
            "    ],",
            "    targets: [",
            '        .target(name: "SizeTarget", dependencies: [',
            *[f"            {dep}," for dep in target_deps],
            "        ]),",
            "    ]",
            ")",
            "",
        ]
    )


def write_target(
    work: Path, package: str, spec: Spec | None, version: str, pins: dict[str, str]
) -> Path:
    """Write the SizeTarget package next to a fresh copy of the static app project."""
    target = work / "SizeTarget"
    sources = target / "Sources" / "SizeTarget"
    sources.mkdir(parents=True, exist_ok=True)
    (target / "Package.swift").write_text(
        manifest(spec, version, pins), encoding="utf-8"
    )
    entry = HERE / "entries" / f"{'baseline' if spec is None else package}.swift"
    shutil.copyfile(entry, sources / "Entry.swift")
    app = work / "SizeApp"
    if not app.exists():
        shutil.copytree(HERE / "SizeApp", app)
    return target


def tag_dates(repositories: Path) -> dict[str, dict[str, int]]:
    """Map each cloned package's origin URL identity to {tag: unix creation time}."""
    dates: dict[str, dict[str, int]] = {}
    for clone in repositories.iterdir():
        url = run(
            ["git", "-C", str(clone), "config", "--get", "remote.origin.url"]
        ).strip()
        refs = run(
            [
                "git",
                "-C",
                str(clone),
                "for-each-ref",
                "refs/tags",
                "--format=%(refname:short) %(creatordate:unix)",
            ]
        )
        dates[identity(url)] = {
            name: int(stamp)
            for name, stamp in (
                line.split(" ", 1) for line in refs.splitlines() if " " in line
            )
        }
    return dates


def pin_versions(target: Path) -> list[tuple[str, str, str]]:
    """(identity, location, version) for every version-pinned package of the last resolve."""
    data = json.loads((target / "Package.resolved").read_text(encoding="utf-8"))
    pins = []
    for pin in data["pins"]:
        version = pin["state"].get("version")
        if isinstance(version, str):
            pins.append((str(pin["identity"]), str(pin["location"]), version))
    return pins


def release_day_version(current: str, tags: dict[str, int], cutoff: int) -> str | None:
    """The newest stable tag of the same major on or before cutoff, if current postdates it."""
    current_tag = next((t for t in tags if t.lstrip("v") == current), None)
    current_semver = semver(current)
    if current_tag is None or current_semver is None or tags[current_tag] <= cutoff:
        return None
    candidates = [
        (parsed, name)
        for name, stamp in tags.items()
        if stamp <= cutoff
        and (parsed := semver(name)) is not None
        and parsed[0] == current_semver[0]
        and parsed < current_semver
    ]
    if not candidates:
        raise MeasureError(
            f"{current} postdates the release and has no earlier release"
        )
    return max(candidates)[1].lstrip("v")


def resolve_or_drop_conflict(
    target: Path, scratch: Path, pins: dict[str, str]
) -> str | None:
    """Resolve; on a conflict with one of pins, drop that pin and return its identity."""
    resolved = subprocess.run(  # nosec B603 B607 - fixed executable, no shell
        ["swift", "package", "resolve", "--scratch-path", str(scratch)],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    if resolved.returncode == 0:
        return None
    conflict = PIN_CONFLICT.search(resolved.stderr + resolved.stdout)
    location = next(
        (url for url in pins if conflict and identity(url) == conflict[1]), None
    )
    if location is None:
        sys.stderr.write(resolved.stdout[-4000:] + resolved.stderr[-4000:])
        raise MeasureError(f"swift package failed ({resolved.returncode})")
    log(
        f"dropping pin {identity(location)} {pins.pop(location)}: an exact requirement wins"
    )
    return identity(location)


def release_day_pins(
    target: Path, scratch: Path, spec: Spec, version: str
) -> dict[str, str]:
    """Pin every transitive dependency to the newest version a consumer could get on release day.

    Range requirements resolve to today's newest version, which postdates an old release. Each
    dependency resolved past the measured tag's date is pinned back to the newest stable tag of
    the same major on or before that date, then the graph is re-resolved until it is stable.

    Pinning two packages independently can contradict an exact requirement between them (UX
    Helper 0.10.1 needs dcui-swift-schema exactly 2.5.0, while 2.6.0 also predates the release).
    That pin is then dropped for good: the dependent's own requirement names a version that
    existed when the dependent was released, which is earlier still.
    """
    tag = f"{spec.tag_prefix}{version}"
    pins: dict[str, str] = {}
    fixed = {identity(spec.url)} | {identity(c.url) for c in spec.companions}
    for _ in range(MAX_PIN_ROUNDS):
        (target / "Package.swift").write_text(
            manifest(spec, version, pins), encoding="utf-8"
        )
        dropped = resolve_or_drop_conflict(target, scratch, pins)
        if dropped:
            fixed.add(dropped)
            continue
        dates = tag_dates(scratch / "repositories")
        cutoff = dates[identity(spec.url)].get(tag)
        if cutoff is None:
            raise MeasureError(f"tag {tag} has no date")
        changed = False
        for pin_id, location, current in pin_versions(target):
            if pin_id in fixed:
                continue
            earlier = release_day_version(current, dates.get(pin_id, {}), cutoff)
            if earlier is not None:
                pins[location] = earlier
                changed = True
        if not changed:
            return pins
    raise MeasureError("dependency pins did not settle")


def build(work: Path, kind: str) -> Path:
    """Archive the app as a consumer ships it (stripped, Release, arm64) and return the .app."""
    archive = work / f"{kind}.xcarchive"
    run(
        [
            "xcodebuild",
            "archive",
            "-project",
            str(work / "SizeApp" / "SizeApp.xcodeproj"),
            "-scheme",
            "SizeApp",
            "-configuration",
            "Release",
            "-destination",
            "generic/platform=iOS",
            "-archivePath",
            str(archive),
            "-derivedDataPath",
            str(work / f"dd-{kind}"),
            "-clonedSourcePackagesDirPath",
            str(work / f"spm-{kind}"),
            "ARCHS=arm64",
            "ONLY_ACTIVE_ARCH=NO",
            "CODE_SIGN_IDENTITY=-",
            "CODE_SIGNING_REQUIRED=NO",
            "CODE_SIGNING_ALLOWED=NO",
            "-quiet",
        ]
    )
    app = archive / "Products" / "Applications" / "SizeApp.app"
    if not app.is_dir():
        raise MeasureError(f"no app in {archive}")
    return app


def bundle_bytes(app: Path) -> int:
    """Summed file sizes in the bundle; du would count allocated blocks instead."""
    return sum(
        path.lstat().st_size
        for path in app.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def metrics(app: Path) -> dict[str, int]:
    """App bundle bytes and main executable bytes."""
    return {
        "app_bundle_bytes": bundle_bytes(app),
        "executable_bytes": (app / "SizeApp").stat().st_size,
    }


def measure_baseline(work: Path) -> dict[str, int]:
    """Build and measure the empty app."""
    write_target(work, "baseline", None, "", {})
    sizes = metrics(build(work, "baseline"))
    log(f"baseline: {sizes['app_bundle_bytes']} bytes")
    if sizes["app_bundle_bytes"] > MAX_BASELINE_BYTES:
        raise MeasureError(
            f"baseline is {sizes['app_bundle_bytes']} bytes, expected under {MAX_BASELINE_BYTES}"
        )
    return sizes


def measure_with(
    work: Path, package: str, version: str
) -> tuple[dict[str, int], dict[str, str]]:
    """Build and measure the app with the package, and return its sizes and resolved versions."""
    spec = SPECS[package]
    target = write_target(work, package, spec, version, {})
    pinned = release_day_pins(target, work.parent / "resolve", spec, version)
    resolved = {name: current for name, _, current in pin_versions(target)}
    for name, current in sorted(resolved.items()):
        note = (
            " (pinned to release day)"
            if any(identity(u) == name for u in pinned)
            else ""
        )
        log(f"resolved {name} {current}{note}")
    sizes = metrics(build(work, "with"))
    log(f"with {package} {version}: {sizes['app_bundle_bytes']} bytes")
    return sizes, resolved


def measure(package: str, version: str, work: Path) -> dict[str, object]:
    """Build the baseline and the app with the package, and return the contract's JSON object."""
    baseline = measure_baseline(work / "baseline")
    with_package, resolved = measure_with(work / "with", package, version)
    added = with_package["app_bundle_bytes"] - baseline["app_bundle_bytes"]
    if added < SPECS[package].floor_bytes:
        raise MeasureError(
            f"{package} adds {added} bytes, expected at least {SPECS[package].floor_bytes}; "
            "it has probably stopped linking"
        )
    return {
        "platform": "ios",
        "package": package,
        "version": version,
        "toolchain": " ".join(run(["xcodebuild", "-version"]).split()),
        "metrics": {
            name: {"baseline": value, "with": with_package[name]}
            for name, value in baseline.items()
        },
        "resolved": resolved,
    }


def main(argv: list[str]) -> int:
    """Entry point: measure one package version and print its JSON."""
    if len(argv) != 2 or argv[0] not in SPECS or semver(argv[1]) is None:
        log(f"usage: measure.sh <{'|'.join(SPECS)}> <version>")
        return 2
    package, version = argv[0], argv[1].lstrip("v")
    keep = os.environ.get("SIZE_REPORT_WORK_DIR")
    work = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="size-report-ios-"))
    try:
        result = measure(package, version, work)
    except MeasureError as error:
        log(f"NOT MEASURED: {error}")
        return 1
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
