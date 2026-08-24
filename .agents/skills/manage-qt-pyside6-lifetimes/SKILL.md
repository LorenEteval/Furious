---
name: manage-qt-pyside6-lifetimes
description: Audit and implement safe Qt/PySide6 object ownership and destruction in Furious. Use for QObject/UI lifetimes, transient or reusable windows, signals/slots, direct bound-method connections, weak dispatch, delete-on-close dialogs, timers, models, delegates, registries, stale wrappers, memory growth, premature destruction, and native-versus-Nuitka packaged differences.
---

# Manage Qt/PySide6 Lifetimes

Treat lifetime correctness as part of the implementation, not as a later cleanup step. Fix the ownership model instead of masking symptoms.

## Required reference

Before changing or reviewing lifetime-relevant code, read [references/qt-pyside6-object-lifetime-guidelines.md](references/qt-pyside6-object-lifetime-guidelines.md) completely. Apply its detailed requirements together with the scoped `AGENTS.md` files.

## Workflow

### 1. Inventory the lifetime graph

For every affected Qt object, record:

- creator and durable Python owner;
- `QObject` parent;
- intended category: long-lived, reusable, or transient;
- close/hide/destroy path;
- timers, event filters, models, delegates, menus, actions, animations, and graphics effects it owns;
- connections to application-lifetime senders;
- for each relevant signal: sender/receiver lifetimes and QObject trees, direct bound method versus weak dispatcher versus closure/partial, and its disconnect boundary;
- caches, registries, closures, partials, lambdas, or callbacks that can retain it.

Do not treat `.show()`, `.open()`, `.close()`, a parent, or a weak reference as proof that the lifetime is correct.

### 2. Trace both failure directions

Check for retention:

- closed transient UI still reachable from controllers, globals, registries, signals, timers, callbacks, or caches;
- Qt children hidden but never destroyed;
- native resources, worker threads, or handles outliving the feature.

Check for premature destruction:

- asynchronous top-level windows created only in a local variable;
- Python wrappers collected while the C++ object should remain usable;
- stale Python references after Qt deletes the native object.

### 3. Choose one intentional ownership model

- **Long-lived:** create once under an application-lifetime owner and shut down explicitly.
- **Reusable:** retain one strong owner, hide/show deliberately, reset state when reopened, and destroy with the owner.
- **Transient:** retain while visible, preserve normal close/accept/reject behavior, destroy after the interaction, and release owning references on destruction.

Use `WA_DeleteOnClose`, explicit disconnection, `deleteLater()`, or `removeEventFilter()` only when that specific model requires it.

### 4. Audit indirect ownership

Search the affected call paths for:

- `lru_cache`, `cache`, memoization, and object-keyed dictionaries;
- module/application/controller/plugin registries;
- nested functions, bound methods, lambdas, and `functools.partial`;
- `QTimer`, `installEventFilter`, `QAction`, `QMenu`, `QActionGroup`, `QShortcut`, models, delegates, and watchers;
- long-lived signals connected to transient Python callables.

Prefer immutable metadata and classes/factories in caches and registries. Never cache a transient Qt instance or an instance method whose key contains `self`.

### 5. Enforce packaged signal safety

Nuitka's PySide6 integration can retain compiled bound methods passed directly to
`SignalInstance.connect()` in a process-global protection list. A connection that is
harmless under native CPython can therefore retain a transient receiver and its Qt
subtree for the life of the packaged process.

- Do not connect a signal directly to a bound method of a transient or repeatedly
  created `QObject`.
- Use `Furious.Qt.connectWeakly(signal, receiver, 'methodName', ...)`.
- Pass `sender=` when the sender is independently owned or longer-lived so the helper
  can remove the dormant dispatcher when the receiver is destroyed. Use
  `forwardSender=True` instead of relying on `QObject.sender()` when the slot needs the
  sender.
- Do not substitute a lambda or partial that strongly captures the receiver.
- Direct bound-method connections are acceptable only for deliberately process-lifetime
  receivers when the resulting strong retention is intentional and documented.

The weak dispatcher must keep only weak receiver/sender references, check PySide wrapper
validity, and resolve the method by name at emission time.

### 6. Preserve asynchronous dialog destruction

For non-blocking dialogs, distinguish interaction completion from native destruction:

- reusable dialogs may release an open-dialog registry entry at `finished`;
- one-shot dialogs using `WA_DeleteOnClose` must remain strongly retained after
  `finished`, through deferred Qt deletion, until `destroyed` has been dispatched;
- release the registry entry on the next event-loop turn after `destroyed`;
- registry callbacks must capture an opaque lifetime token, not the dialog;
- operation-specific context may be released at `finished` once callbacks no longer
  need it.

Use the existing `AppQDialog`/`AppQTransientDialog`/`AppQMessageBox` ownership model
rather than adding a parallel registry.

### 7. Diagnose before fixing

Use targeted evidence as needed:

- `weakref.ref` or `weakref.finalize`;
- `QObject.destroyed`;
- live instance/resource counters;
- `gc.get_referrers`, `gc.get_objects`, or `tracemalloc`;
- repeated create/open/close cycles;
- exact process handle, thread, timer, action, and menu counts.

Distinguish retained objects from Python allocator high-water marks and Qt/native memory caching. Remove temporary diagnostics after the cause is understood.

### 8. Verify the lifecycle

Run the narrow behavior test first, then the applicable Qt lifetime tier in `tests/README.md`. For shared transient infrastructure, repeat at least 20-50 cycles and verify:

- every intended `destroyed` signal fires;
- weak references and registries return to baseline;
- timers/actions/menus/threads/handles do not grow linearly;
- reusable windows remain valid across reopen cycles;
- asynchronous windows retain a Python owner while visible;
- native Python remains correct and the packaged build is checked when the issue is packaging-specific.

For transient signal/dialog infrastructure, run both the native lifecycle tests and a
Nuitka-compiled repeated-open/close probe. Cover `accept`, `reject`, and window-close
paths plus representative protocol/editor mixes. Assert that destroyed counts match,
weak wrappers and registries return to zero, operation context is released, no invalid
wrapper is accessed, and Nuitka's protected callback collection does not grow when that
internal diagnostic is observable. If it is hidden by the compiled runtime, combine
zero retained wrappers with inspection of the selected Nuitka package configuration;
do not report an unobservable counter as measured.

## Prohibited shortcuts

Do not use routine `gc.collect()`, global retention of every window, indiscriminate `WA_DeleteOnClose`, hiding instead of destroying, broad deleted-wrapper exception suppression, or ever-growing thresholds as standalone fixes.

## Completion checklist

Before handing off a Qt-related change, be able to explain:

1. the Python owner and Qt parent;
2. the intended lifetime category;
3. the exact destruction or reuse path;
4. why signals, timers, filters, caches, and registries cannot retain stale UI;
5. why the object cannot disappear prematurely;
6. whether direct signal callbacks or closures create unwanted packaged-build retention;
7. for delete-on-close dialogs, why the final owner survives until native destruction;
8. which native and, when relevant, Nuitka-compiled lifecycle verification passed.
