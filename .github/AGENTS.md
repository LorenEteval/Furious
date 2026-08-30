# Release workflow guidance

## Publication and matrix contract

- `workflows/deploy-pypi.yml` is both packaging coverage and the publication graph. Pull requests and ordinary pushes
  build artifacts; tag pushes additionally publish Python distributions, create the GitHub release, and enable the
  dependent WinGet flow. Preserve permission, secret, environment, `if`, and `needs` boundaries.
- Treat each matrix row as a supported product target with explicit runner OS/architecture, Python, Qt/PySide source,
  native-binding toolchain, compatibility floor, `Deploy.py` output, and upload pattern. Artifact names and architecture
  checks must agree; never infer target architecture from the host label alone.
- Current target-specific assertions are intentional: Linux proves an Essentials-only/no-WebEngine application and its
  Flatpak sandbox dependencies; macOS verifies its WebEngine frameworks, helpers, resources, relocation, and signing;
  Windows verifies native imports and every packaged PE machine type, with a separate Windows 7 compatibility toolchain.
  Change an exception only with evidence from the affected target.

## Workflow engineering

- Keep packaging declarations synchronized with `Deploy.py`, `pyproject.toml`, `setup.py`, and `requirements.txt`.
  Default-to-newest dependencies still need deterministic assertions at ABI/feature boundaries; pin or checksum external
  build tools where the workflow establishes a supply-chain boundary.
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
