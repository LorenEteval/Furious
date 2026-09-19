# Furious test suite

The suite uses Python's built-in `unittest` runner. Run it from the repository
root with the project dependencies installed in an existing virtual environment.
Tests cover source behavior, real Qt interactions, and resource ownership; they
do not establish that a packaged build or every supported Python/Qt version works.

## Setup and quick start

Activate an existing root `.venv*` or `venv*` environment before using the commands
below. To reproduce the dependency selection in
[the source CI workflow](../.github/workflows/source-tests.yml), use:

```text
python -m pip install -r requirements.txt "PySide6-Essentials==6.8.3" "PySide6-Addons==6.8.3"
```

CI uses Python 3.13. Linux CI also installs `libegl1` and `libopengl0` for Qt.
Backend Python packages in `requirements.txt` are import dependencies; tests do
not require separately installed proxy-core executables or a working proxy.

Select the offscreen platform **before starting Python**. Some test modules
import Qt-backed Furious modules before `tests.support` can set its defensive
default. Use a fresh Python process for each invocation and do not use `python -O`:
several child scripts and the standalone lifetime probe use plain `assert`.

PowerShell:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
python -m unittest discover -s tests -v
```

Command Prompt:

```cmd
set QT_QPA_PLATFORM=offscreen
set PYTHONUTF8=1
python -m unittest discover -s tests -v
```

POSIX shell:

```sh
export QT_QPA_PLATFORM=offscreen
export PYTHONUTF8=1
python -m unittest discover -s tests -v
```

Default discovery includes the regular Qt/process stress tests. Very-heavy cases
are discovered but skipped unless explicitly enabled. An inherited opt-in
variable also affects focused module runs; clear it when returning to the default
tier. Standalone benchmark and fixture entrypoints are not run by discovery.

For a focused module, class, or method:

```text
python -m unittest tests.test_endpoint_info -v
python -m unittest tests.test_endpoint_info.EndpointInfoServiceTest -v
python -m unittest tests.test_controllers.RoutingControllerTest.testDisabledCustomRoutingStaysOnFallbackAfterReenable -v
```

## Coverage map

The tables list every `test_*.py` module. Areas overlap: a service module may also
contain a small UI workflow, and a Qt test may exercise persistence or a real
worker. Choose tests by the changed contract rather than by filename alone.

### Models, persistence, plugins, and protocols

| Module | Coverage |
| --- | --- |
| [test_interface.py](test_interface.py) | Stable exit/runtime contracts, configuration serialization and diagnostics, editor binding, live storage ownership. |
| [test_models_and_services.py](test_models_and_services.py) | Profile identity/copies/fingerprints, legacy metadata, repository round trips, settings migration, bounded logs and metrics, translation extraction. |
| [test_repository_contracts.py](test_repository_contracts.py) | Routing/TUN/subscription persistence, stable filtered moves, remote ownership detachment, atomic hydration, malformed-storage preservation, private-data diagnostics. |
| [test_plugin_architecture.py](test_plugin_architecture.py) | Registry creation, API-v3 capabilities and prepared runtimes, atomic registration/rollback, failure isolation, shutdown, transient editor ownership. |
| [test_public_api.py](test_public_api.py) | Curated package exports, compatibility imports, and lazy bundled backend discovery in isolated child interpreters. |
| [test_hysteria1_protocol.py](test_hysteria1_protocol.py) | URI/mapping compatibility, plugin/editor discovery, independent download-test configuration. |
| [test_hysteria2_compatibility.py](test_hysteria2_compatibility.py) | Compact editor mappings and defaults, unknown/JSON-only fields, ECH/Gecko/Realm/Mimic URI and configuration handling, full runtime JSON, editor destruction. |
| [test_backend_editor_contract.py](test_backend_editor_contract.py) | Observational editor loading, unsupported Hysteria1/Xray values, Xray transport alias normalization. |
| [test_shadowsocks_uri.py](test_shadowsocks_uri.py) | SIP002 encoding, IPv6/Unicode/plugin fields, deterministic generated round trips, malformed-input rejection. |
| [test_socks_uri.py](test_socks_uri.py) | Canonical and legacy/Base64 SOCKS forms, strict decoding, IPv6, aliases, Xray/plugin/subscription integration. |

### Application, controllers, and services

| Module | Coverage |
| --- | --- |
| [test_application_process.py](test_application_process.py) | Exact application-child ownership, shared crash flag, exception/signal handling, temporary crash logs, command-line dispatch. |
| [test_architecture_refactors.py](test_architecture_refactors.py) | Startup acquisition/rollback including partial controller construction and cleanup retry, singleton election and real isolated IPC race, tray/exit policy, host integration ownership, bounded core-log transport, connection transactions, stylesheet composition. |
| [test_connection_startup_async.py](test_connection_startup_async.py) | Real local-listener readiness, timeout/cancel/replacement, semantic exits, DNS reply lifetime, mocked platform-specific TUN sequencing. |
| [test_controllers.py](test_controllers.py) | Connection state/error/reconnect transitions, startup restoration, shared settings, routing fallback persistence and tray/selector agreement after custom-routing disable/re-enable. |
| [test_runtime_lifecycle.py](test_runtime_lifecycle.py) | Qt-thread exit dispatch, commit/exit races, duplicate and late exits, idempotent release, spawn failure, queue/timer disposal on preparation failure. |
| [test_external_core.py](test_external_core.py) | Harmless real process launch/output/shutdown, partial thread-start rollback, non-finite timeout rejection, readiness/TUN metadata, Windows paths with spaces, subscription rejection of executable profiles, bounded DNS references. |
| [test_frozenlib.py](test_frozenlib.py) | Nested state guards, cleanup isolation, bounded caches/throttling, dual-stack probe selection, mocked proxy/DNS/routes/startup/session boundaries and failure handling. |
| [test_native_tun_semantics.py](test_native_tun_semantics.py) | Xray/Hysteria2 runtime-copy TUN preservation/replacement, managed-TUN failures, download-test stripping, prevention of a second tun2socks owner. |
| [test_subscription_sync.py](test_subscription_sync.py) | Group-local preparation/commit, stable duplicate identity, atomic failure, preservation of newer local metadata, rejection of changed source state. |
| [test_subscription_manager.py](test_subscription_manager.py) | Stable request generations, provider metadata, batch/partial failures, timer policy, targeted updates, real Stop Updates input, worker responsiveness, cancellation and synchronous shutdown ownership. |
| [test_subscription_scalability.py](test_subscription_scalability.py) | Deterministic 1/3/8-group preparation and commit with 1,500 profiles per group and bounded workers; uses the offline benchmark helper. |
| [test_profile_test_jobs.py](test_profile_test_jobs.py) | Stable profile/fingerprint jobs, stale results, endpoint deduplication, bounded fan-out, adaptive Tcping, download scheduling, reusable Stop All, real pool/thread teardown and retry, narrow cell repaint. |
| [test_service_runtime.py](test_service_runtime.py) | Update-response validation, HTTP timeouts/context release/reentrant destruction, duplicate completion, plugin-page registration, bounded connectivity requests, blocked statistics-worker callback lifetime. |
| [test_xray_asset_download.py](test_xray_asset_download.py) | Checksum validation, atomic asset replacement, real pool delivery, early owner destruction, callback release, plugin shutdown. |
| [test_endpoint_info.py](test_endpoint_info.py) | Opt-in proxy-only discovery using fake HTTP responses, fallback/cache/session invalidation, privacy/presentation controls, local map styling and persistent-scene contracts. |
| [test_metrics_behavior.py](test_metrics_behavior.py) | Immutable time-series history, pruning/buckets, usage versus speed clearing, hidden-page rendering, graph hover lookup. |
| [test_log_manager_generation.py](test_log_manager_generation.py) | Reference-model state transitions, concurrency, live/retired ownership, bounded FIFO cleanup, structural complexity, incremental/multiline LogPage rendering; also contains an opt-in generation campaign. |
| [test_log_manager_benchmark.py](test_log_manager_benchmark.py) | Data-only report validation, workload compatibility, timing ratios, and real standalone CLI JSON round trips; no performance gates or historical imports. |

### Qt behavior, layout, and lifetime

| Module | Coverage |
| --- | --- |
| [test_isolation_and_navigation.py](test_isolation_and_navigation.py) | Nested/canonical QSettings sandbox checks, outside-path rejection, navigation overlay geometry, dismissal, page/object reuse. |
| [test_main_window_geometry.py](test_main_window_geometry.py) | First-show lifecycle, restored/default/legacy geometry, main/routing window reuse, session-only navigation state, protection of never-shown windows' saved geometry. |
| [test_dialog_geometry.py](test_dialog_geometry.py) | Dialog show/open/exec preparation, sizing/centering, failure cleanup, specialized message-box geometry and transient destruction. |
| [test_layout_matrix.py](test_layout_matrix.py) | Navigation and message-box layouts in fresh processes at scale factors 1, 1.25, 1.5, and 2, under both themes. |
| [test_ui_behavior.py](test_ui_behavior.py) | Translation and editor mappings, settings organization, stable server/routing moves, real QR rendering/decoding, incremental log filtering/tail behavior, connected-routing change notices, message boxes, shared Home/tray state. |
| [test_qt_interactions.py](test_qt_interactions.py) | Real keyboard/mouse/focus and proxy mapping, scoped shortcuts, sorting/selection, stable subscription deletion confirmations, debounced Home search, Tests-menu selection color, shared settings, batched profile mutation and cancellation. |
| [test_qr_export_scalability.py](test_qr_export_scalability.py) | Production capture cap, immediate single export, incremental yielding, failure/cancel/close paths, immutable snapshots, window-owned state destruction. |
| [test_stylesheet_states.py](test_stylesheet_states.py) | Targeted rendering/alpha/geometry assertions for table/list insets, popup corners, clear buttons, focus/disabled states, and stylesheet composition. |
| [test_theme_transition.py](test_theme_transition.py) | Real cross-fades, immediate theme activation, interruption, per-window resize/destruction, coordinator teardown, animation policy. |
| [test_qt_lifetime.py](test_qt_lifetime.py) | Native destruction and weak-wrapper/registry evidence across dialogs, menus, actions, timers, signals, message-box buttons/masks, owner-first confirmations, reusable editors, simulated compiled-method retention. |

### Repeated stress and release confidence

| Module | Coverage |
| --- | --- |
| [test_qt_stress.py](test_qt_stress.py) | Warmed-up dialog batches, real editor families, native/wrapper/registry counts, Python/RSS trends, repeated real QR exports at the production cap. |
| [test_process_stress.py](test_process_stress.py) | Repeated real Python-backed external-core start/stop, exact child reaping, pipes/readers/watchers, thread/handle checks and RSS reporting. |
| [test_very_heavy.py](test_very_heavy.py) | Explicitly enabled high-count plugin/application-child/external-core lifecycles, metrics/logs/navigation, transient dialogs/message boxes, and 1,000 real QR tabs. |

## Selecting tiers

Full discovery is the most reliable way to include all source modules. For
focused work, these smaller groups collectively cover the suite; they are
convenience commands, not separate runners or markers. The generation module's
regular cases run by default while its heavy class remains gated.

```text
# Models, storage, plugin API, protocol/editor compatibility
python -m unittest tests.test_interface tests.test_models_and_services tests.test_repository_contracts tests.test_plugin_architecture tests.test_public_api tests.test_hysteria1_protocol tests.test_hysteria2_compatibility tests.test_backend_editor_contract tests.test_shadowsocks_uri tests.test_socks_uri -v

# Application, connection, runtime, and mocked host boundaries
python -m unittest tests.test_application_process tests.test_architecture_refactors tests.test_connection_startup_async tests.test_controllers tests.test_runtime_lifecycle tests.test_external_core tests.test_frozenlib tests.test_native_tun_semantics -v

# Subscription, profile tests, HTTP/assets, endpoint information, metrics, and logs
python -m unittest tests.test_subscription_sync tests.test_subscription_manager tests.test_subscription_scalability tests.test_profile_test_jobs tests.test_service_runtime tests.test_xray_asset_download tests.test_endpoint_info tests.test_metrics_behavior tests.test_log_manager_generation tests.test_log_manager_benchmark -v

# Real Qt input, presentation, rendering, geometry, and lifetime
python -m unittest tests.test_isolation_and_navigation tests.test_main_window_geometry tests.test_dialog_geometry tests.test_layout_matrix tests.test_ui_behavior tests.test_qt_interactions tests.test_qr_export_scalability tests.test_stylesheet_states tests.test_theme_transition tests.test_qt_lifetime -v

# Regular repeated stress: no opt-in required; also runs in default discovery
python -m unittest tests.test_qt_stress tests.test_process_stress -v

# Release-confidence classes: set the opt-in below before starting Python
python -m unittest tests.test_very_heavy tests.test_log_manager_generation.VeryHeavyGenerationLogManagerTest -v
```

To check suspected order dependence, pass the affected module names in the
opposite order in one invocation, then run default discovery in a fresh process.
Passing modules in separate processes cannot expose leaked shared Qt/repository
state between those modules.

### Very-heavy opt-in

Set `FURIOUS_VERY_HEAVY_TESTS` to exactly `1` **before discovery/import**. It enables
both `VeryHeavyContractTest` and `VeryHeavyGenerationLogManagerTest`.

PowerShell:

```powershell
$env:FURIOUS_VERY_HEAVY_TESTS = '1'
python -m unittest discover -s tests -v
Remove-Item Env:FURIOUS_VERY_HEAVY_TESTS
```

POSIX shell:

```sh
FURIOUS_VERY_HEAVY_TESTS=1 python -m unittest discover -s tests -v
```

Command Prompt users can set `FURIOUS_VERY_HEAVY_TESTS=1` with `set`, and clear it
with `set FURIOUS_VERY_HEAVY_TESTS=` afterward.

All discovered tests use the checked-out implementation. No Git history or
historical source execution is required. The optional log timing comparison is
a standalone benchmark using saved JSON reports, described below.

The generation campaign mixes exact structural/backlog assertions with relative
scaling gates and reported latency distributions. Its long soak reports RSS
samples; that report is not itself an RSS-plateau assertion. Record interpreter,
Qt, OS, workload, and opt-ins when interpreting timings. Benchmarks and packaged
smoke checks remain separate when the very-heavy tier is enabled.

## Isolation and interpreting results

[tests/support.py](support.py) supplies the shared harness:

- `application()` creates one small test `QApplication`; it does not compose the
  normal application runtime, singleton, tray, or host integration.
- `isolatedSettings()` uses unique temporary INI identities and restores the
  caller's identity. `assertIsolatedSettings()` compares canonical paths, including
  macOS temporary-directory aliases and Windows short names. In-memory `Storage`
  collections still need their own fixture isolation/restoration.
- `processQtEvents()` drains regular/deferred-delete events; `waitFor()` pumps
  until a bounded deadline and returns a boolean that callers must check.
  `collectAtBoundary()` is a diagnostic collection boundary, not a production
  cleanup technique or a replacement for native destruction evidence.
- `runPythonChild()` captures one exact interpreter child's output with a timeout.
  `childEnvironment()` copies the caller environment and forces offscreen Qt;
  the child fixture must still disable or replace host effects and production
  persistence before exercising application paths.
- `currentRSS()` and `currentNativeHandleCount()` use Windows APIs or Linux
  `/proc` counters. They currently return `None` on macOS; unavailable counters
  mean unmeasured, not zero. Object, registry, thread, and exit assertions remain
  useful independently of those counters.

Normal tests do not need external network access and must not change real proxy,
TUN, DNS, routing, startup registration, production settings, or unrelated
processes. HTTP/provider responses and privileged host boundaries are faked or
mocked. Some tests deliberately use **real isolated local IPC, loopback listeners,
threads, and child processes**: the singleton race has a unique socket name, and
readiness tests own their local listener. Cleanup targets only resources created
by that test. Mocked platform branches prove call/ownership contracts, not actual
OS integration.

Use real Qt input/event delivery for focus, selection, shortcuts, proxy mapping,
and destruction. Targeted pixel/alpha assertions are appropriate when rendering
is the contract; arbitrary whole-window snapshots or fixed timing guesses are
not substitutes for state and ownership assertions.

On CI's Qt 6.8.3 runtime, [fixtures/offscreen.json](fixtures/offscreen.json) gives
the shared application a 1920×1080 virtual desktop. Geometry tests account for
translated controls' minimum sizes. Popup tests explicitly restore window
activation where offscreen macOS does not, selection-color checks avoid glyphs
and respect image scaling, and log catch-up waits for queued scrolling as well
as document updates. QR yielding checks do not rely on the relative ordering of
zero-delay timers.

Two cases are Windows-only: the native-session finalization regression in
`test_architecture_refactors.py` and executable-path-with-spaces coverage in
`test_external_core.py`. Other platforms report those as skips. The latter uses
a temporary copy of the base interpreter and its DLLs, including across volumes.

Expected negative-path warnings/errors can accompany a passing run. Capture
expected errors with `assertLogs` when their text is part of the contract; the
malformed TUN-settings test does this to prevent an expected traceback becoming
a misleading GitHub problem-matcher annotation. Check the runner's final result,
exit code, and skip reasons. An exception inside a Qt-dispatched callback can
reach `sys.excepthook` without failing unittest, so reentrant/destruction tests
must capture and assert callback errors as well.

Cancellation, logical completion, and resource release are different assertions.
For example, subscription Stop Updates rejects late work but running preparation
remains owned until it returns. Its slow-shutdown warning is not an exit deadline.
The profile-test shutdown regression checks independent Tcping/download cleanup
and a later retry while a Ping worker is gated; it does not prove arbitrary
third-party work can always be forcibly stopped.

The two paused-log examples in `test_ui_behavior.py` are commented out alongside
the disabled Pause/Resume Updates feature. They are neither discovered tests nor
reported skips. Re-enable them together with the feature.

## Standalone benchmarks and fixtures

[benchmarks/benchmark_log_manager.py](benchmarks/benchmark_log_manager.py) measures
steady append, core rollover, category/global snapshots, and retention-heavy
append using the current checkout. Save a baseline before a change, then compare
with another report using the same workload and machine/toolchain:

```text
python -m tests.benchmarks.benchmark_log_manager --output baseline.json
python -m tests.benchmarks.benchmark_log_manager --baseline baseline.json --output current.json
```

`--entries` defaults to 50,000 and must match the saved baseline. Reports include
the workload schema, entry count, Python/Qt/platform metadata, and timings. Ratios
are current/baseline (below 1 means faster); they are informational, not test
thresholds. Only compatible JSON data is read: the benchmark never looks up Git
revisions or imports historical source. Run measurements in fresh processes and
keep both reports outside tracked source. Timing noise and environment changes
still require interpretation; older ad-hoc comparison output is not this report
format. The benchmark has no unittest opt-in variable.

[benchmarks/benchmark_subscription_updates.py](benchmarks/benchmark_subscription_updates.py)
generates offline data by default and measures decode/parse, reconciliation
preparation, worker wall time, and sequential commit time. The `decode_cpu_s`
and `reconcile_cpu_s` fields sum elapsed worker durations measured with
`perf_counter`; they are not process CPU-time measurements. `gui_commit_s`
measures caller-thread commit work, not a rendered GUI workflow.

```text
python -m tests.benchmarks.benchmark_subscription_updates --profiles 1500 --groups 1,3,8
```

Its optional `--url` downloads a live subscription and is an explicit networked
benchmark mode, not part of normal tests. The discovered scalability test calls
the offline helper and checks counts/worker bounds without elapsed-time gates.

[benchmarks/benchmark_qr_export.py](benchmarks/benchmark_qr_export.py) measures
real Segno-to-`QImage` rendering and synchronous/incremental QR windows. Run each
mode in a fresh process to avoid sharing allocator/widget state:

```text
python -m tests.benchmarks.benchmark_qr_export --mode images --count 5000
python -m tests.benchmarks.benchmark_qr_export --mode synchronous --count 5000
python -m tests.benchmarks.benchmark_qr_export --mode asynchronous --count 5000 --timeout 900
```

These large UI workloads are benchmarks, distinct from correctness tests. Regular
QR stress uses the production cap; the very-heavy QR case temporarily raises it
to 1,000 and verifies yielding, visible presentation, completion, and destruction.

[fixtures/editor_lifetime_probe.py](fixtures/editor_lifetime_probe.py) is a
self-contained source/compiled lifecycle probe using the shared harness, without
importing the unittest modules. Run the representative editor sequence through
each completion path:

```text
python -m tests.fixtures.editor_lifetime_probe --iterations 100 --pattern representative --close-method close
python -m tests.fixtures.editor_lifetime_probe --iterations 100 --pattern representative --close-method accept
python -m tests.fixtures.editor_lifetime_probe --iterations 100 --pattern representative --close-method reject
```

Patterns also include `alternating`, `reverse`, `hysteria2`, and `vless`. The
representative pattern cycles through Hysteria2, VLESS, VMess, Trojan, SOCKS,
Hysteria1, and External Core. Each invocation additionally probes HTTP completion
and owner/reply-first destruction, button ownership, signal endpoints, masks,
reopen generations, animations, menus, and view-owned confirmations. It records
JSON diagnostics and asserts captured Qt callback exceptions are absent.

For compiler-sensitive work, compile this fixture separately with Nuitka's
PySide6 plugin, its imported support code, and required data, then repeat the
close/accept/reject checks. Record the Python/PySide6/Nuitka versions, target, and
build flags. A missing private protected-method counter is unknown, not zero;
combine available diagnostics with native destruction, weak-wrapper, and registry
evidence. A diagnostic build passing does not establish that an ordinary release
build has the same behavior.

## CI and packaged validation

[Source regression CI](../.github/workflows/source-tests.yml) runs default
discovery on `ubuntu-22.04`, `windows-2025`, and `macos-14`, with Python 3.13,
PySide6 Essentials/Addons 6.8.3, offscreen Qt, and a 30-minute job timeout.
[The publication workflow](../.github/workflows/deploy-pypi.yml) requires this job
before PyPI publication. CI does not enable the very-heavy opt-in,
run standalone benchmarks, or compile the lifetime fixture. This matrix does
not validate every Python/Qt floor declared by the package.

For a packaged smoke check, use a disposable OS account or VM, redirect settings
and application data to temporary locations, and keep system proxy/TUN disabled.
Exercise the ordinary release artifact as well as any diagnostic build. Open and
close representative transient editors repeatedly, verify reusable
`TextEditorWindow` close/show cycles do not duplicate actions, and inspect
ownership/destruction evidence. Close only the exact process started for the
check. Source-suite success and release import checks do not replace packaged
behavior or real desktop integration testing.

When reporting verification, separate source execution, mocked platform evidence,
opt-in stress/benchmark output, and packaged/manual results. Include skipped or
unavailable cases and targets rather than presenting discovery alone as execution.
