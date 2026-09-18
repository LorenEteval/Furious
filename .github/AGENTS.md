# Release workflow guidance

Inherit repository-wide rules from the root `AGENTS.md`. This scope owns build/publication evidence and target-specific
exceptions; it does not define the source test suite or imply that every package dependency is pinned.

## Publication and matrix contract

- `workflows/deploy-pypi.yml` is both packaging coverage and the publication graph. Pull requests and ordinary pushes
  build artifacts; tag pushes additionally publish Python distributions, create the GitHub release, and enable the
  dependent WinGet flow. Preserve permission, secret, environment, `if`, and `needs` boundaries.
- `workflows/daily-matrix-build.yml` owns the shared binary matrix, called by `workflows/deploy-pypi.yml` and also run daily or
  manually. Its standalone runs build, verify, and upload artifacts with read-only repository permissions; publication
  remains in `workflows/deploy-pypi.yml`.
- Treat each matrix row as a supported product target with explicit runner OS/architecture, Python, Qt/PySide source,
  native-binding toolchain, compatibility floor, `Deploy.py` output, and upload pattern. Artifact names and architecture
  checks must agree; never infer target architecture from the host label alone.
- Current target-specific assertions are intentional: Linux proves an Essentials-only/no-WebEngine application and its
  Flatpak sandbox dependencies; macOS verifies its WebEngine frameworks, helpers, resources, relocation, and signing;
  Windows verifies native imports and every packaged PE machine type, with a separate Windows 7 compatibility toolchain.
  Change an exception only with evidence from the affected target. Binary jobs filter shared requirements before
  installing target-specific Qt/native bindings; copying the ordinary package dependency list into those jobs can
  reintroduce Addons on Linux or replace a compatibility build. Review the effective installed set, not just the
  checked-in requirements.

## Workflow engineering

- Keep packaging declarations synchronized with `Deploy.py`, `pyproject.toml`, `setup.py`, and `requirements.txt`.
  The Python floor advertised by package metadata is a separate claim from the interpreter versions exercised by CI;
  newer matrix rows cannot prove that floor. Likewise, successful Qt imports do not prove event-loop or binding-call
  compatibility. Default-to-newest dependencies/assets still need recorded provenance and deterministic assertions
  at ABI/feature boundaries; pin or checksum external build tools where the workflow establishes that boundary.
- The workflow default shell is Bash, including Windows jobs. Select PowerShell explicitly for native Windows paths,
  process APIs, or PowerShell syntax, and keep OS/architecture conditions on the step that owns the difference.
- Flatpak checks run inside the installed sandbox, inspect the application's required native closure rather than every
  unused Qt plugin, and fail before upload. Do not mask an actually loadable plugin/runtime mismatch with a broad allowlist.
- Generated helper files, downloaded SDKs/assets, build directories, and local bundles are disposable workflow inputs;
  do not commit them. Never expose credentials or enable publication from untrusted pull-request code.

## Verification

- Validate YAML and every affected expression/shell. Trace each changed matrix row through dependency installation,
  source/native import checks, Nuitka/installer output, packaged architecture/dependency checks, artifact upload, and tag
  gates. When a target cannot run locally, add a narrow CI assertion that fails before publication with a useful reason.
- The current workflow performs packaging/import/native checks but does not run the unittest behavioral suite. Do
  not call an artifact build a regression-test pass; use `tests/README.md` for source verification. Check actual
  `needs` and tag gates rather than assuming a downstream publish job runs on every build. Follow each publication
  dependency back to its required artifact checks; upload success alone does not establish release eligibility.
- Revalidate version/architecture claims against the current matrix instead of duplicating all pins here. When build
  topology intentionally changes, update this scope and follow every consumer through upload and publication.
