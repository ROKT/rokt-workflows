#!/usr/bin/env bash
# Measures what one published iOS SDK release adds to an empty SwiftUI app. See ../README.md.
# Usage: measure.sh <package> <version>
set -euo pipefail
exec python3 "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/measure_ios.py" "$@"
