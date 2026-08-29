# Furious test suite

The suite uses Python's built-in `unittest` runner. In the main test process,
Qt tests use one deliberately small `QApplication` and route `QSettings` to a
unique temporary directory. Focused lifecycle, public-import, and display-scale
regressions may start a hermetic child Python process, and external-runtime tests use that child interpreter as
a harmless stand-in for a core. Tests do not initialize Furious's singleton IPC
server, production repositories, system proxy, TUN, routing, update network
clients, or real proxy cores.

## Testing philosophy

Choose the smallest layer that can prove the contract under test. Do not replace
Qt behavior with direct slot calls when focus, selection, model mapping, shortcut
scope, event delivery, or destruction is part of that contract.

1. **Pure logic tests** exercise models, repositories, codecs, controllers, and
   services without constructing widgets. Inject only the runtime, network, or
   host-operation boundary that would otherwise cause an external side effect.
2. **Qt integration tests** construct the real widget/model/proxy composition and
   use `QTest` keyboard or mouse input plus the real event loop. Assertions target
   semantic state such as profile identity, current selection, focus owner,
   signal count, and wrapper destruction—not incidental row numbers or pixels.
3. **Small workflow tests** compose a few real UI surfaces around one shared
   controller or repository. They keep Qt signals and widgets real while mocking
   only unavailable platform privileges, network/process launch, plugin discovery,
   or user-facing host dialogs.

`tests.support` is the canonical Qt harness: `application()` owns the one
process-wide test application, `isolatedSettings()` contains persistence,
`processQtEvents()` drains deferred deletion, and `waitFor()` handles bounded
event-loop convergence. Add a helper there only when multiple modules need the
same lifecycle primitive; do not create a second application or event-pumping
strategy in an individual test.

## Coverage map

| Area | Principal tests |
| --- | --- |
| Configuration, profiles, migration, repositories | `test_models_and_services.py`, `test_repository_contracts.py` |
| Generation log invariants, model fuzzing, concurrency, reclamation, complexity, and opt-in soak/latency probes | `test_log_manager_generation.py` |
| Low-level application, runtime, editor, and storage contracts | `test_interface.py` |
| Application composition, startup rollback, connection ownership, entry-point and crash boundaries | `test_architecture_refactors.py`, `test_application_process.py` |
| Plugin registration, capability dispatch, factories, rollback, and Hysteria1 ownership | `test_plugin_architecture.py`, `test_hysteria1_protocol.py` |
| Controller state and error transitions with injected runtimes | `test_controllers.py` |
| SOCKS and SIP002 Shadowsocks codecs and generated round trips | `test_socks_uri.py`, `test_shadowsocks_uri.py` |
| Subscription workflow, timers, stale requests, and reconciliation | `test_subscription_manager.py`, `test_subscription_sync.py` |
| External process launch, output, shutdown, threads, TUN metadata | `test_external_core.py` |
| Backend structured-editor observational load and unknown-value preservation | `test_backend_editor_contract.py` |
| Xray asset checksum validation and atomic replacement | `test_xray_asset_download.py` |
| Xray/Hysteria2 native-TUN ownership and proxy-only stripping | `test_native_tun_semantics.py` |
| Rolling metrics, stable buckets, lazy rendering, and hover | `test_metrics_behavior.py` |
| Proxy-only endpoint discovery, caching, and presentation | `test_endpoint_info.py` |
| Bounded service work, update validation, plugin UI, and worker lifetime | `test_service_runtime.py` |
| Frozenlib state helpers and mocked platform-operation boundaries | `test_frozenlib.py` |
| Settings sandbox, navigation overlay behavior, public exports, and scale/theme isolation | `test_isolation_and_navigation.py`, `test_public_api.py`, `test_layout_matrix.py` |
| Theme cross-fade activation, interruption, multi-window cleanup, and animation policy | `test_theme_transition.py` |
| AppQMainWindow lifecycle, subclass policies, geometry restoration, and migration | `test_main_window_geometry.py` |
| AppQDialog first-presentation geometry, native show paths, centering, and async lifetime | `test_dialog_geometry.py` |
| Editor mappings, lazy log rendering, routing/message-box/connection UI | `test_ui_behavior.py` |
| Real keyboard/mouse/focus, proxy mapping, shared Home/Settings state, and transient editor input | `test_qt_interactions.py` |
| Direct Qt ownership and destruction across independent UI families | `test_qt_lifetime.py` |
| Batched real/probe Qt object, handle, Python allocation, and RSS trends | `test_qt_stress.py` |
| Repeated harmless subprocess, pipe, thread, handle, and RSS trends | `test_process_stress.py` |
| Opt-in release-confidence counts (100 app children, 100 external cores, 100k metrics, 40k logs, 20k navigation, 5k plugins, 1k dialogs) | `test_very_heavy.py` |

The lifecycle tests classify `AppQTransientDialog`, protocol/plugin editors,
routing dialogs, subscription editors, message boxes, QR windows, and TUN
settings dialogs as transient. `TextEditorWindow` is intentionally reusable: it
must survive normal close/show cycles without multiplying actions, and is then
explicitly destroyed by its owner. Main pages/controllers are application
lifetime objects and are tested through isolated service/UI boundaries rather
than by starting the production application runtime.

## Commands

Run commands from the repository root with the project and its runtime
dependencies installed in the active environment. If the root contains a
`.venv*` or `venv*` environment, activate it first; the examples intentionally
use its `python` command rather than a machine-specific interpreter path.

Select the offscreen Qt platform **before Python starts**. Some test modules
import Qt-backed Furious modules before `tests.support` can apply its defensive
default, so setting it only after test discovery begins is too late.

Windows PowerShell:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
```

Windows Command Prompt:

```cmd
set QT_QPA_PLATFORM=offscreen
```

Linux, macOS, and other Unix-compatible shells:

```sh
export QT_QPA_PLATFORM=offscreen
```

Then run the desired test tier.

```text
# Complete suite, including repeated lifetime/process stress tests
python -m unittest discover -s tests -v

# Regular logic, persistence, plugin, controller, codec, and UI regressions
python -m unittest tests.test_interface tests.test_models_and_services tests.test_repository_contracts tests.test_architecture_refactors tests.test_plugin_architecture tests.test_hysteria1_protocol tests.test_hysteria2_compatibility tests.test_controllers tests.test_subscription_manager tests.test_subscription_sync tests.test_socks_uri tests.test_shadowsocks_uri tests.test_backend_editor_contract tests.test_xray_asset_download tests.test_native_tun_semantics tests.test_metrics_behavior tests.test_endpoint_info tests.test_service_runtime tests.test_frozenlib tests.test_isolation_and_navigation tests.test_main_window_geometry tests.test_dialog_geometry tests.test_ui_behavior tests.test_qt_interactions tests.test_stylesheet_states tests.test_theme_transition tests.test_public_api -v

# Direct Qt/process integration and destruction/lifetime checks
python -m unittest tests.test_application_process tests.test_external_core tests.test_layout_matrix tests.test_qt_lifetime -v

# Explicit repeated stress tier
python -m unittest tests.test_qt_stress tests.test_process_stress -v

# Explicit release-confidence tier (skipped unless opted in)
# PowerShell: $env:FURIOUS_VERY_HEAVY_TESTS = '1'
# POSIX shell: export FURIOUS_VERY_HEAVY_TESTS=1
python -m unittest tests.test_very_heavy -v

# Generation-specific release-confidence campaign (same opt-in switch)
python -m unittest tests.test_log_manager_generation.VeryHeavyGenerationLogManagerTest -v

# Shared-state order-independence spot check
python -m unittest tests.test_public_api tests.test_theme_transition tests.test_stylesheet_states tests.test_qt_interactions tests.test_ui_behavior tests.test_dialog_geometry tests.test_main_window_geometry tests.test_isolation_and_navigation tests.test_frozenlib tests.test_service_runtime tests.test_endpoint_info tests.test_metrics_behavior tests.test_native_tun_semantics tests.test_xray_asset_download tests.test_backend_editor_contract tests.test_shadowsocks_uri tests.test_socks_uri tests.test_subscription_sync tests.test_subscription_manager tests.test_controllers tests.test_hysteria2_compatibility tests.test_hysteria1_protocol tests.test_plugin_architecture tests.test_architecture_refactors tests.test_repository_contracts tests.test_models_and_services tests.test_interface -v
python -m unittest discover -s tests -v
```

To run one module, class, or method while developing, pass its dotted test name
to the same runner, for example:

```text
python -m unittest tests.test_endpoint_info -v
python -m unittest tests.test_endpoint_info.EndpointInfoServiceTest -v
```

No external network access or separately installed Xray/Hysteria executable is
required. Process-boundary tests create only temporary scripts and launch the
active Python interpreter. Two regressions cover Windows-specific behavior and
are skipped on other platforms; native handle/RSS trend checks use the safe
platform counters available on the current host.

Several negative-path tests intentionally emit warning or error log messages.
The opt-in release-confidence tier uses high operation counts but samples native
resources only at batch boundaries, so its assertions remain ownership-oriented.
Neither stress tier is enabled by a normal focused module run. Treat the runner's
final status and exit code as authoritative; expected diagnostic output still ends in
`OK`.

## Packaged-build smoke procedure

Packaged/Nuitka behavior is outside the source-level `unittest` fixtures. For an
optional release smoke check, use an otherwise disposable test OS account or
VM, redirect all Furious application-data/settings locations to a temporary
directory, and keep system proxy and TUN disabled. Open and close each transient
editor family 50 times, verify one reusable `TextEditorWindow` does not
duplicate actions, and compare live-object diagnostics from an instrumented
build before/after the loop. Do not run this procedure against a production
profile or rely on process-name cleanup; close only the exact packaged process
started for the smoke test.

## Isolation rules

- Tests clean up only exact subprocess handles/PIDs and threads they create.
- Child-process lifecycle tests disable single-instance discovery and host
  integration before running a real Qt event loop.
- Tests never search for, signal, or terminate another Furious/core process.
- Persistence tests use temporary INI-backed `QSettings` namespaces.
- Controller tests inject fake runtime managers and patch host-mutation APIs.
- Qt tests use normal close/deferred-delete paths and collect Python cycles only
  at diagnostic batch boundaries, never once per UI operation.
- A lifetime failure must be investigated as an ownership defect; increasing
  thresholds or forcing production garbage collection is not an acceptable fix.
