# TODO

## CI: checks on pull requests

- [x] `.github/workflows/ci.yml`, triggered on `pull_request` and on `push` to `main`
- [x] Run `pytest` on `ubuntu-latest` — the suite is hermetic (no Rekordbox, no database), so it
      does not need a macOS runner
- [x] Matrix over Python 3.11 / 3.12 / 3.13 (`pyproject.toml` claims `>=3.11`, and the bundled
      runtime is 3.12 — all three should stay green)
- [x] Cache pip downloads (`actions/setup-python` with `cache: pip`)
- [x] Lint + format check: add `ruff` (lint and format) and run it in CI, plus `mypy` on
      `src/spectro_rb` if the type coverage is worth it
- [x] Compile the Swift app on `macos-latest` (`swift build -c release`) so UI changes cannot
      break the build unnoticed; cache `app/.build`
- [x] `swift-format lint` for the Swift sources
- [x] Guard rail: fail the build if `samples/`, `*.csv`, `master.db` or any `.app` is ever added
      to the repo — these must stay local
- [x] Secret scanning (`gitleaks`) — cheap insurance given the app touches a personal library
- [x] Set `permissions: contents: read` and a `concurrency` group that cancels superseded runs

## CI: build the app on push to main

- [x] `.github/workflows/build-app.yml`, triggered on `push` to `main` (and `workflow_dispatch`)
- [x] Runs `./scripts/build_app.sh` on `macos-latest`
- [x] Cache the python-build-standalone tarball (`build/cache`) keyed on `PBS_TAG` + `PY_VERSION`
      so every run does not re-download ~70 MB
- [x] Zip `dist/SpectroRB.app` (`ditto -c -k --keepParent`, which preserves the bundle) and upload
      it with `actions/upload-artifact`; set a short retention, the artifact is ~129 MB
- [x] Smoke test the built bundle in CI: `SpectroRB.app/Contents/Resources/python/bin/spectro-rb doctor --json`
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

- [x] Dependabot for GitHub Actions and pip
- [x] Pin third-party actions to commit SHAs
- [ ] PR template and a short CONTRIBUTING note
- [ ] Add a `Makefile` or `justfile` wrapping the common commands (`test`, `lint`, `build-app`)
- [ ] README: add a badge and a note that released builds are unsigned until notarisation is set up

## Write the Spectro metrics into the Rekordbox comment (opt-in)

`confidence_pct` and `cutoff_khz` are already parsed, matched and reported, but they only
exist outside Rekordbox — in the `--report` CSV and the `--json` stream. Putting them in
`DjmdContent.Commnt` makes them a sortable, searchable browser column, so a suspect track
can be judged in the place where the decision actually gets made.

This is the first feature that would write a second field, so it stays off by default.

- [ ] `--annotate` / **Write quality notes to comments** toggle; without it, behaviour is
      byte-for-byte what it is today (`ColorID` only)
- [ ] Append a delimited block to the existing comment rather than replacing it, e.g.
      `whatever the user wrote [SPX FAKE 78% 16.1kHz]`, with `trusted` shown as
      `[SPX FAKE 100% 19.9kHz trusted]`
- [ ] Idempotent: re-syncing must rewrite the block in place, never stack a second one.
      Match on the `[SPX …]` delimiter and treat everything outside it as untouchable
- [ ] `--strip-annotations` to remove every block the tool ever wrote, so the feature is
      fully reversible without restoring a backup
- [ ] A track with no row in the CSV is never touched — no stale-block cleanup, no sweep.
      Exports are typically incremental (only newly added tracks get run through Spectro),
      so "absent from the CSV" means "not analysed this time", never "no longer suspect".
      This matches how `ColorID` already behaves; `--strip-annotations` is the only way a
      block is ever removed.
- [ ] Extend the empirical diff check in the README the same way `ColorID` was verified:
      apply to a copy, diff all 75 columns, prove only `Commnt` and `ColorID` moved
- [ ] Update the safety table in the README — the "colour only" guarantee becomes
      "colour only, unless you explicitly ask for comments"

Rejected alternatives, recorded so they don't get re-proposed:

- **Rekordbox MyTags** (`DjmdMyTag` + `DjmdSongMyTag`) would give real filter checkboxes,
  which is the nicest UX by some distance — but it needs a tag tree created up front and
  pyrekordbox's write support there is thin. Revisit once the comment path is proven.
- **File tags** (ID3 `TXXX` / Vorbis comments) are durable and portable, but Rekordbox
  won't show them without a *Reload Tags*, which clobbers other rekordbox-side metadata.
  Wrong trade for a field that exists to be glanced at in the browser.

## Product ideas (vnext)

- [ ] Remember the last CSV and the overwrite preference between launches
- [ ] Configurable verdict → colour mapping in the UI
- [ ] Undo: restore a chosen backup from within the app
- [ ] Watch a folder for new Spectro exports and sync automatically
- [ ] Write the unmatched report from the app without a save dialog round-trip
