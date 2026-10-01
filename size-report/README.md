# Release size report

Measures what a **published** SDK release adds to a consumer's app, and writes the result into
that release's GitHub description. The same method runs at release time and for backfilling
older releases, so every number in every release body is comparable with every other.

## Method

- **Published artifacts only.** A version is measured as a consumer receives it: a Maven Central
  coordinate on Android, an SPM tag on iOS. Never the source checkout. This is also what makes a
  backfill possible.
- **One fixed toolchain per platform**, pinned in this directory, so a toolchain upgrade is a
  deliberate change here rather than drift between releases.
- **One starting app per platform**, shared by every package:
  - Android: a small Compose + Material3 screen (`android/src/main`). Almost every partner app
    already ships Compose, so an empty app would charge the SDKs for it.
  - iOS: an empty SwiftUI app. SwiftUI ships with the OS, so there is nothing to subtract.
- **Size impact = app with the package − the starting app**, both built by the same toolchain.
- Each package's fixture calls a real entry point, so the shrinker (Android) or linker (iOS)
  keeps what a real integration keeps.

## Packages

| Id                       | Android                                           | iOS                                                   |
| ------------------------ | ------------------------------------------------- | ----------------------------------------------------- |
| `mparticle-core`         | `com.mparticle:android-core`                      | `mparticle-apple-sdk`, product `mParticle-Apple-SDK`  |
| `mparticle-rokt-kit`     | `com.mparticle:android-rokt-kit`                  | `mp-apple-integration-rokt`, product `mParticle-Rokt` |
| `rokt-sdk-plus`          | `com.rokt:rokt-sdk-plus`                          |                                                       |
| `rokt-sdk`               | `com.rokt:roktsdk`                                | `rokt-sdk-ios`, product `Rokt-Widget`                 |
| `rokt-payment-extension` | `com.rokt:roktsdk` + `com.rokt:payment-extension` | `rokt-payment-extension-ios`, from 5.2.4              |
| `rokt-ux-helper`         | `com.rokt:roktux`                                 | `rokt-ux-helper-ios`, product `RoktUXHelper`          |

Each id names the whole stack a consumer pulls in: `mparticle-rokt-kit` includes the Core SDK and
the Rokt SDK, and `rokt-sdk` includes UX Helper. A kit or payment extension is always measured with
the core SDK or Rokt SDK of the same version.

`repos.json` says which packages each repository's releases report. A row's optional third field is
the first version that package exists in; older releases leave the row out rather than showing
"not measured" for something that was never published. The iOS SDK+ umbrella
(`ROKT/rokt-sdk-plus-ios`) is not measured yet.

## Measurement output

`android/measure.sh <package> <version>` and `ios/measure.sh <package> <version>` each print one
line of JSON on stdout. Everything else goes to stderr.

```json
{
  "platform": "android",
  "package": "rokt-ux-helper",
  "version": "2.0.5",
  "toolchain": "AGP 8.9.1, Kotlin 2.1.20, Compose BOM 2026.05.01",
  "metrics": {
    "apk_bytes": { "baseline": 1300934, "with": 2254471 },
    "download_bytes": { "baseline": 1240062, "with": 2190034 },
    "dex_bytes": { "baseline": 1829108, "with": 3580332 }
  }
}
```

- Android metrics: `apk_bytes` (the archive), `download_bytes` (summed compressed entries),
  `dex_bytes` (uncompressed code).
- iOS metrics: `app_bundle_bytes` (summed file sizes in the `.app`), `executable_bytes` (the main
  binary).
- iOS adds a `resolved` object naming the version of each transitive dependency it built with. A
  dependency declared as a range is pinned to the newest version tagged on or before the measured
  release's tag date: what a consumer resolving that release on release day would have got.

A version that does not exist, does not build, or fails a plausibility floor prints **nothing**
and exits non-zero. The release section then says "not measured" rather than showing a
fabricated saving.

## Release section

`render_release_size.py` turns the JSON for a release, and for the release before it, into a
section delimited by `<!-- size-impact:start -->` and `<!-- size-impact:end -->`.
`update_release_body.py` replaces that section in an existing body, or appends it, so re-running
is idempotent and the rest of the body is never touched.
