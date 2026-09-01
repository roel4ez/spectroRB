# TODO

## CI: checks on pull requests

- [ ] `.github/workflows/ci.yml`, triggered on `pull_request` and on `push` to `main`
- [ ] Run `pytest` on `ubuntu-latest` — the suite is hermetic (no Rekordbox, no database), so it
      does not need a macOS runner
- [ ] Matrix over Python 3.11 / 3.12 / 3.13 (`pyproject.toml` claims `>=3.11`, and the bundled
      runtime is 3.12 — all three should stay green)
- [ ] Cache pip downloads (`actions/setup-python` with `cache: pip`)
- [ ] Lint + format check: add `ruff` (lint and format) and run it in CI, plus `mypy` on
      `src/spectro_rb` if the type coverage is worth it
- [ ] Compile the Swift app on `macos-latest` (`swift build -c release`) so UI changes cannot
      break the build unnoticed; cache `app/.build`
- [ ] `swift-format lint` for the Swift sources
- [ ] Guard rail: fail the build if `samples/`, `*.csv`, `master.db` or any `.app` is ever added
      to the repo — these must stay local
- [ ] Secret scanning (`gitleaks`) — cheap insurance given the app touches a personal library
- [ ] Set `permissions: contents: read` and a `concurrency` group that cancels superseded runs

## CI: build the app on push to main

- [ ] `.github/workflows/build-app.yml`, triggered on `push` to `main` (and `workflow_dispatch`)
- [ ] Runs `./scripts/build_app.sh` on `macos-latest`
- [ ] Cache the python-build-standalone tarball (`build/cache`) keyed on `PBS_TAG` + `PY_VERSION`
      so every run does not re-download ~70 MB
- [ ] Zip `dist/SpectroRB.app` (`ditto -c -k --keepParent`, which preserves the bundle) and upload
      it with `actions/upload-artifact`; set a short retention, the artifact is ~129 MB
- [ ] Smoke test the built bundle in CI: `SpectroRB.app/Contents/Resources/python/bin/spectro-rb doctor --json`
      must exit 0 and report no database (no Rekordbox on the runner)

## Before the app is shareable with anyone else

- [ ] **Universal binary.** `build_app.sh` currently builds for the host architecture only, both
      for Swift and for the Python runtime. Intel Macs need either a `universal2` build
      (`swift build --arch arm64 --arch x86_64` + both PBS tarballs merged) or two separate artifacts.
- [ ] **Signing and notarisation.** The bundle is ad-hoc signed, so anyone else gets a Gatekeeper
      block. Needs a Developer ID certificate in secrets, `codesign --options runtime`,
      `xcrun notarytool submit` and `xcrun stapler staple`.
- [ ] Decide on a distribution format (zip vs DMG) and add a release workflow triggered on tags
      that attaches the artifact to a GitHub Release.
- [ ] Single source of truth for the version — it is currently duplicated in `pyproject.toml`,
      `src/spectro_rb/__init__.py` and `app/Resources/Info.plist`.
- [ ] An app icon (`AppIcon.icns` + `CFBundleIconFile`); the bundle has none.

## Testing gaps worth closing

- [ ] There is no test for `discovery.py` (database auto-detection) — it can be covered with a
      temp directory and fake `master.db` files
- [ ] There is no test for `backup.py` — worth asserting that `-wal`/`-shm` sidecars are copied
      and that the timestamped folder is created
- [ ] `guard.py` is only exercised manually; the `ps` parsing can be tested by injecting output
- [ ] Nothing exercises `Rekordbox6Database` itself. That is deliberate: the database is
      SQLCipher-encrypted and personal, so it can never be a CI fixture. Keep the boundary in
      `rekordbox.py` thin enough that everything above it stays testable with fakes.
- [ ] Add coverage reporting so the untested modules above are visible

## Repository housekeeping

- [ ] Dependabot for GitHub Actions and pip
- [ ] Pin third-party actions to commit SHAs
- [ ] PR template and a short CONTRIBUTING note
- [ ] Add a `Makefile` or `justfile` wrapping the common commands (`test`, `lint`, `build-app`)
- [ ] README: add a badge and a note that released builds are unsigned until notarisation is set up

## Product ideas (vnext)

- [ ] Remember the last CSV and the overwrite preference between launches
- [ ] Configurable verdict → colour mapping in the UI
- [ ] Undo: restore a chosen backup from within the app
- [ ] Watch a folder for new Spectro exports and sync automatically
- [ ] Write the unmatched report from the app without a save dialog round-trip
