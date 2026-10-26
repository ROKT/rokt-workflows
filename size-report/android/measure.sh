#!/usr/bin/env bash
# Measures what one published version of an SDK package adds to a minified release APK. Prints
# one line of JSON on stdout (see ../README.md); everything else goes to stderr so stdout stays
# parseable. Prints nothing and exits non-zero if the version cannot be measured.
#
# Usage: measure.sh <package> <version>
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

log() { echo "$*" >&2; }

if [[ $# -ne 2 ]]; then
    log "Usage: measure.sh <package> <version>"
    exit 2
fi
PACKAGE="$1"
VERSION="$2"

# Floors sit well below the observed figures, so they catch a package that silently stopped
# linking rather than tracking normal drift. A collapsed delta would otherwise read as a saving.
MIN_BASELINE_BYTES=$((768 * 1024))
case "${PACKAGE}" in
mparticle-core) MIN_IMPACT_BYTES=$((100 * 1024)) ;;
rokt-ux-helper | rokt-sdk) MIN_IMPACT_BYTES=$((512 * 1024)) ;;
mparticle-rokt-kit) MIN_IMPACT_BYTES=$((768 * 1024)) ;;
rokt-payment-extension | rokt-sdk-plus) MIN_IMPACT_BYTES=$((3 * 1024 * 1024)) ;;
*)
    log "Unknown package: ${PACKAGE}"
    exit 2
    ;;
esac

build() {
    log "Assembling ${PACKAGE} ${VERSION}..."
    rm -rf "${SCRIPT_DIR}/build/${PACKAGE}/outputs"
    (
        cd "${SCRIPT_DIR}"
        ./gradlew assembleBaselineRelease assembleTargetRelease \
            -Psize.package="${PACKAGE}" -Psize.version="${VERSION}" --no-daemon --quiet
    ) >&2
}

# AGP writes output-metadata.json beside the APK; reading it survives the `-unsigned` suffix.
apk_path() {
    local flavor="$1"
    local dir="${SCRIPT_DIR}/build/${PACKAGE}/outputs/apk/${flavor}/release"
    python3 -c 'import json,sys; print(sys.argv[2] + "/" + json.load(open(sys.argv[1]))["elements"][0]["outputFile"])' \
        "${dir}/output-metadata.json" "${dir}"
}

# One pass over the archive: its own length, the summed compressed entries (the closest portable
# proxy for what a user downloads), and the uncompressed dex.
apk_metrics() {
    python3 - "$1" <<'PY'
import json, os, sys, zipfile

path = sys.argv[1]
with zipfile.ZipFile(path) as archive:
    entries = archive.infolist()
print(json.dumps({
    "apk_bytes": os.path.getsize(path),
    "download_bytes": sum(entry.compress_size for entry in entries),
    "dex_bytes": sum(entry.file_size for entry in entries if entry.filename.endswith(".dex")),
}))
PY
}

toolchain() {
    sed -n -e "s/.*id 'com.android.application' version '\(.*\)'/AGP \1/p" \
        -e "s/.*id 'org.jetbrains.kotlin.android' version '\(.*\)'/Kotlin \1/p" \
        -e "s/.*platform('androidx.compose:compose-bom:\(.*\)')/Compose BOM \1/p" \
        "${SCRIPT_DIR}/build.gradle" | paste -sd ',' - | sed 's/,/, /g'
}

main() {
    if ! build; then
        log "Build failed for ${PACKAGE} ${VERSION}: it may not be published, or not build here."
        return 1
    fi
    local baseline target
    baseline="$(apk_metrics "$(apk_path baseline)")"
    target="$(apk_metrics "$(apk_path target)")"

    # Before emitting, not after: a failure here must leave stdout empty.
    python3 - "${PACKAGE}" "${VERSION}" "$(toolchain)" "${baseline}" "${target}" \
        "${MIN_BASELINE_BYTES}" "${MIN_IMPACT_BYTES}" <<'PY'
import json, sys

package, version, toolchain, baseline, target, min_baseline, min_impact = sys.argv[1:]
baseline, target = json.loads(baseline), json.loads(target)
impact = target["apk_bytes"] - baseline["apk_bytes"]
if baseline["apk_bytes"] < int(min_baseline):
    sys.exit(f"IMPLAUSIBLE: starting app is {baseline['apk_bytes']} bytes; R8 has probably "
             "shrunk Compose out of it. Check HostActivity still renders.")
if impact < int(min_impact):
    sys.exit(f"IMPLAUSIBLE: {package} {version} adds {impact} bytes, expected at least "
             f"{min_impact}. Check its entry point in packages/{package}.")
print(json.dumps({
    "platform": "android",
    "package": package,
    "version": version,
    "toolchain": toolchain,
    "metrics": {key: {"baseline": baseline[key], "with": target[key]} for key in baseline},
}))
PY
}

main
