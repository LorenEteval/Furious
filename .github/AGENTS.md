# Release workflow guidance

## Matrix and artifact contract

- `workflows/deploy-pypi.yml` is both continuous packaging coverage and the publication pipeline. Pull requests and
  ordinary pushes build distributions; tag pushes additionally publish to PyPI, create the GitHub release, and feed the
  downstream WinGet step through job dependencies. Preserve that gate when changing `if` or `needs` relationships.
- Treat every matrix row as a supported environment with its own Python, architecture, Qt, native-binding, and packaging
  constraints. Keep runner architecture, Python architecture, dependency source/binary policy, `Deploy.py` artifact
  naming, and upload patterns aligned. Do not infer support from the host OS alone.
- Linux releases intentionally install PySide6 Essentials without Addons/WebEngine and verify the map fallback plus the
  packaged absence of WebEngine. macOS intentionally includes and verifies WebEngine bundle resources/symlinks/signing.
  Windows verifies native imports and every packaged PE machine type; Windows 7 also uses its patched toolchain and
  compatibility DLL. Preserve the reason for a platform exception when updating versions or dependencies.

## Safe workflow changes

- Pin or integrity-check downloaded build tools where the workflow already establishes a trust boundary. Keep
  credentials in GitHub permissions, environments, and secrets; never print tokens or move publication into an
  untrusted pull-request path.
- The workflow default shell is Bash even on Windows runners; select PowerShell explicitly for steps that require native
  Windows paths, process APIs, or PowerShell syntax. Keep OS/architecture conditions at the step that owns the exception.
- Workflow-generated helper files and downloaded assets are disposable inputs. Do not commit them, and keep networked
  asset refresh separate from hermetic unit tests. Changes to workflow dependencies or artifacts normally require a
  matching review of `Deploy.py`, `pyproject.toml`, `setup.py`, and `requirements.txt`.
- Validate YAML and shell syntax, evaluate every affected OS/architecture condition, and run the closest local source or
  packaging check available. For changes that cannot be reproduced locally, make the CI assertion explicit so a wrong
  architecture, missing module, unexpected Qt feature, or absent artifact fails before publication.
