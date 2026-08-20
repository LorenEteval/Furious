# Furious test suite

The suite uses Python's built-in `unittest` runner. Qt tests select the
`offscreen` platform before importing PySide6, construct one deliberately small
test `QApplication`, and route `QSettings` to a unique temporary directory.
They do not initialize Furious's singleton IPC server, production repositories,
system proxy, TUN, routing, update network clients, or real proxy cores.

## Coverage map

| Area | Principal tests |
| --- | --- |
| Configuration, profiles, migration, repositories | `test_models_and_services.py` |
| Low-level application, runtime, editor, and storage contracts | `test_interface.py` |
| Plugin registration, capability dispatch, factories, rollback | `test_plugin_architecture.py` |
| Controller state and error transitions with injected runtimes | `test_controllers.py` |
| SOCKS/SIP002 Shadowsocks codecs and generated round trips | `test_socks_uri.py`, `test_shadowsocks_uri.py` |
| Subscription-group reconciliation and ownership isolation | `test_subscription_sync.py` |
| External process launch, output, shutdown, threads, TUN metadata | `test_external_core.py` |
| Xray/Hysteria2 native-TUN ownership and proxy-only stripping | `test_native_tun_semantics.py` |
| Rolling metrics, stable buckets, lazy rendering, and hover | `test_metrics_behavior.py` |
| Proxy-only endpoint discovery, caching, and presentation | `test_endpoint_info.py` |
| Bounded service work, update validation, plugin UI, and worker lifetime | `test_service_runtime.py` |
| Frozenlib state helpers and mocked platform-operation boundaries | `test_frozenlib.py` |
| Settings sandbox and navigation overlay behavior | `test_isolation_and_navigation.py` |
| Editor mappings, lazy log rendering, routing/message-box/connection UI | `test_ui_behavior.py` |
| Direct Qt ownership and destruction across independent UI families | `test_qt_lifetime.py` |
| Batched real/probe Qt object, handle, Python allocation, and RSS trends | `test_qt_stress.py` |
| Repeated harmless subprocess, pipe, thread, handle, and RSS trends | `test_process_stress.py` |

The lifecycle tests classify `AppQTransientDialog`, protocol/plugin editors,
routing dialogs, subscription editors, message boxes, QR windows, and TUN
settings dialogs as transient. `TextEditorWindow` is intentionally reusable: it
must survive normal close/show cycles without multiplying actions, and is then
explicitly destroyed by its owner. Main pages/controllers are application
lifetime objects and are tested through isolated service/UI boundaries rather
than by starting the production application runtime.

## Commands

From the repository root, select the offscreen Qt platform for your shell.

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

Then run the desired test tier. These commands use the active Python
environment, so activate the project's virtual environment first when needed.

```text
# Everything
python -m unittest discover -s tests -v

# Fast logic, persistence, plugin, controller, codec, and UI behavior
python -m unittest tests.test_interface tests.test_models_and_services tests.test_plugin_architecture tests.test_controllers tests.test_subscription_sync tests.test_socks_uri tests.test_shadowsocks_uri tests.test_native_tun_semantics tests.test_metrics_behavior tests.test_endpoint_info tests.test_service_runtime tests.test_frozenlib tests.test_isolation_and_navigation tests.test_ui_behavior -v

# Direct Qt/process integration and destruction/lifetime checks
python -m unittest tests.test_external_core tests.test_qt_lifetime -v

# Explicit slow stress tier
python -m unittest tests.test_qt_stress tests.test_process_stress -v

# Order-independence spot check (reverse the module order, then run all tests)
python -m unittest tests.test_ui_behavior tests.test_isolation_and_navigation tests.test_metrics_behavior tests.test_subscription_sync tests.test_controllers tests.test_plugin_architecture tests.test_models_and_services -v
python -m unittest discover -s tests -v
```

No external network access or installed Xray/Hysteria executable is required.

## Packaged-build smoke procedure

Packaged/Nuitka builds cannot be safely driven by these in-process `unittest`
fixtures. For an optional release smoke check, use an otherwise disposable test
OS account or VM, redirect all Furious application-data/settings locations to a
temporary directory, and keep system proxy and TUN disabled. Open and close each
transient editor family 50 times, verify one reusable `TextEditorWindow` does
not duplicate actions, and compare live-object diagnostics from an instrumented
build before/after the loop. Do not run this procedure against a production
profile or rely on process-name cleanup; close only the exact packaged process
started for the smoke test.

## Isolation rules

- Tests clean up only exact subprocess handles/PIDs and threads they create.
- Tests never search for, signal, or terminate another Furious/core process.
- Persistence tests use temporary INI-backed `QSettings` namespaces.
- Controller tests inject fake runtime managers and patch host-mutation APIs.
- Qt tests use normal close/deferred-delete paths and collect Python cycles only
  at diagnostic batch boundaries, never once per UI operation.
- A lifetime failure must be investigated as an ownership defect; increasing
  thresholds or forcing production garbage collection is not an acceptable fix.
