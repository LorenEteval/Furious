# Qt/PySide6 Object Lifetime Guidelines

## Contents

1. [Core lifetime principle](#1-core-lifetime-principle)
2. [Prevent memory leaks](#2-prevent-memory-leaks)
3. [Be extremely careful with caches](#3-be-extremely-careful-with-caches)
4. [Weak references are not a universal fix](#4-weak-references-are-not-a-universal-fix)
5. [Prevent premature garbage collection](#5-prevent-premature-garbage-collection)
6. [Qt parent ownership must be intentional](#6-qt-parent-ownership-must-be-intentional)
7. [Closing is not always destruction](#7-closing-is-not-always-destruction)
8. [Signals and slots](#8-signals-and-slots)
9. [Timers](#9-timers)
10. [Event filters](#10-event-filters)
11. [Long-lived controllers must not own transient UI](#11-long-lived-controllers-must-not-own-transient-ui)
12. [Plugin and registry design](#12-plugin-and-registry-design)
13. [Dialog and message-box lifetime](#13-dialog-and-message-box-lifetime)
14. [Packaged and compiled builds](#14-packaged-and-compiled-builds-require-extra-caution)
15. [Required lifetime review](#15-required-lifetime-review-for-ui-changes)
16. [Lifetime diagnostics](#16-lifetime-diagnostics)
17. [Stress-test transient UI](#17-stress-test-transient-ui)
18. [Do not mask lifetime bugs](#18-do-not-mask-lifetime-bugs)
19. [Preserve PySide6 wrapper safety](#19-preserve-pyside6-wrapper-safety)
20. [Code review expectation](#20-code-review-expectation)
21. [Acceptance criteria](#acceptance-criteria)

## Purpose

For long-running Qt/PySide6 applications, **object lifetime management is a critical correctness requirement**.

Any change involving `QObject`, `QWidget`, `QDialog`, `QAction`, `QMenu`, `QTimer`, signals/slots, controllers, registries, caches, or dynamically created UI objects must be reviewed for lifetime behavior.

Treat memory leaks, stale object retention, dangling Qt wrappers, and premature garbage collection as serious bugs.

## 1. Core Lifetime Principle

Every `QObject`-derived object should have an intentional owner, lifetime, and destruction strategy. Every signal/callback edge that can extend that lifetime must also have an intentional retention and cleanup strategy.

A packaged PySide6 feature can involve three overlapping lifetime systems:

1. Python wrappers, callables, closures, and reference ownership;
2. Qt/C++ parent ownership, signal dispatch, deferred deletion, and native destruction;
3. compiler/runtime compatibility retention, including Nuitka's protection of selected compiled callbacks.

Correct parentage in one system does not prove that the other two match the intended logical lifetime.

For each dynamically created object, determine which category it belongs to.

### Long-lived objects

Examples:

- main windows;
- persistent pages/views;
- application-wide controllers;
- shared managers/services.

These are expected to live for most or all of the process lifetime. They may have stable ownership through application globals, a long-lived parent `QObject`, or a controller/service owner.

Do not repeatedly recreate long-lived objects unnecessarily.

### Reusable windows/dialogs

These may be opened and closed multiple times while intentionally reusing the same instance.

They require:

- an explicit strong Python owner;
- a clear hide/show lifecycle;
- reset/update logic when reopened.

Do not accidentally destroy a reusable dialog after every close. Do not keep multiple duplicate instances if only one is intended.

### Transient windows/dialogs

These should be created for one interaction and destroyed afterward. Examples include temporary editors, confirmation dialogs, information dialogs, and one-shot configuration dialogs.

Transient objects should not remain strongly referenced after closing. Where appropriate:

- use `WA_DeleteOnClose`;
- call the correct base close implementation;
- remove owning references after destruction;
- stop timers and remove event filters;
- ensure long-lived services do not retain callbacks to them.

Do not blindly apply `WA_DeleteOnClose` to every dialog. Use it only when the intended lifecycle is truly transient.

## 2. Prevent Memory Leaks

When modifying or adding Qt UI code, always consider whether the object can remain alive after it should have been destroyed.

Pay special attention to strong references created by:

- module-level lists, dictionaries, and sets;
- application globals;
- controllers;
- plugin/capability registries;
- factories;
- object pools;
- translation registries;
- signal/slot connections;
- event filters;
- timers;
- `QAction` and `QMenu` ownership;
- closures;
- bound methods;
- partial functions;
- lambda captures;
- caches.

A closed dialog should not remain reachable indefinitely unless reuse is intentional.

## 3. Be Extremely Careful With Caches

Do not use unbounded caches on instance methods of transient UI objects.

A dangerous example:

```python
class Editor:
    @functools.lru_cache(None)
    def groupBoxSequence(self):
        ...
```

The cache key contains `self`, which can retain the entire editor instance and its Qt child tree indefinitely.

For transient `QWidget`, `QDialog`, and `QObject` instances, prefer:

- normal instance attributes;
- immutable cached metadata;
- class-level/static caches that do not contain live instances;
- weak-reference-based structures where appropriate.

Before adding `@lru_cache`, `@cache`, or module-level caches, verify that no transient `QObject` instance can become part of a cache key or cached value.

## 4. Weak References Are Not a Universal Fix

When using `weakref`, verify that:

- weak-reference callbacks do not capture the object strongly;
- bound methods do not accidentally keep the instance alive;
- dead weak references are cleaned up;
- iteration over weak pools handles destroyed objects safely;
- another unrelated container is not still holding a strong reference.

A weak-reference registry cannot fix a leak if another object still owns the widget strongly.

## 5. Prevent Premature Garbage Collection

Lifetime bugs can happen in the opposite direction as well. Never assume that calling `.show()` automatically gives a top-level window a safe Python lifetime.

Dangerous example:

```python
def show_editor(self):
    editor = ServerEditor()
    editor.show()
```

After `show_editor()` returns, the local variable may be the final Python reference. Depending on Qt/PySide6 ownership semantics, the wrapper may then be garbage-collected and the window may immediately disappear, be destroyed unexpectedly, behave inconsistently, or cause wrapper/native-object errors later.

For non-modal top-level widgets/windows, ensure a durable owner exists. Suitable strategies include:

- storing the window as an instance attribute;
- maintaining a managed collection of open windows;
- assigning an appropriate `QObject` parent;
- removing stored references when the object emits `destroyed`;
- using `exec()` for genuinely modal dialogs.

Do not make every window global merely to solve this problem. Choose ownership according to the intended lifecycle.

## 6. Qt Parent Ownership Must Be Intentional

Qt parent/child ownership is not equivalent to application lifecycle correctness. A transient dialog parented to a long-lived widget may remain alive even after being closed.

For every dynamically created widget, ask:

- Who is the `QObject` parent?
- How long does the parent live?
- Does closing destroy the child or only hide it?
- Should the child survive for reuse?
- Does Python also retain a reference?

Do not automatically parent every transient dialog to a main window or another application-lifetime widget.

## 7. Closing Is Not Always Destruction

Calling `.close()` does not necessarily mean an object is destroyed.

Review behavior involving:

- `closeEvent`;
- `accept`;
- `reject`;
- `done`;
- `hide`;
- `deleteLater`;
- `WA_DeleteOnClose`.

Custom lifecycle overrides must call their base implementation when required. An incorrect `closeEvent` override can suppress normal `QDialog` lifecycle signals such as `finished`, `accepted`, and `rejected`.

Do not silently replace Qt lifecycle behavior unless intentional.

## 8. Signals and Slots

Signals and slots can create subtle lifetime relationships. When a transient widget connects to a long-lived object, review whether that connection affects lifetime or can invoke a destroyed receiver.

Examples of long-lived senders include controllers, shared managers/services, application globals, plugin managers, and persistent timers.

Use Qt's automatic `QObject` disconnection where sufficient. When it is not sufficient:

- disconnect explicitly;
- remove callbacks;
- stop timers;
- remove event filters;
- use weak-reference-safe callback patterns.

Avoid unnecessary manual disconnect boilerplate when Qt already manages the connection safely.

### Nuitka/PySide6 compiled bound-method retention

Native PySide6 and a Nuitka-compiled application do not necessarily have the same
Python-callable retention graph. In the currently verified toolchain (Nuitka 4.1.3,
PySide6 6.8.3), Nuitka's standard PySide6 package configuration patches
`SignalInstance.connect()` and `QTimer.singleShot()`. When the callback is a compiled
bound method, the generated post-import code protects it in a process-global list named
`_protected` and may also expose its underlying function on the receiver class. The
compiled runtime does not necessarily publish that list as a `PySide6` module
attribute. This protection keeps the bound receiver strongly reachable. Repeated
transient receivers can therefore grow for the whole packaged-process lifetime even
when native CPython destroys them.

The same protection pattern exists in current upstream Nuitka source. Related PySide6
workaround behavior is documented for earlier Nuitka/PySide6 combinations, but do not
assume an exact introduction version without checking the selected release. Always
inspect the package configuration installed in the environment being shipped.

The following is prohibited for a transient or repeatedly created receiver:

```python
sender.signal.connect(transientReceiver.handleSignal)
QTimer.singleShot(0, transientReceiver.finishWork)
```

Replacing the slot with a lambda or `partial` is not safe if it strongly captures the
receiver:

```python
sender.signal.connect(lambda: transientReceiver.handleSignal())
```

In Furious, use the canonical weak dispatcher:

```python
connectWeakly(
    sender.signal,
    transientReceiver,
    'handleSignal',
    sender=sender,
)
```

`connectWeakly()` has this contract:

- the connected dispatcher is a plain function, not the receiver's bound method;
- receiver and optional sender are stored only through `weakref.ref`;
- the method is resolved by its string name only when the signal is emitted;
- `shiboken6.isValid()` is checked before accessing a `QObject` wrapper;
- `forwardSender=True` explicitly passes the sender instead of depending on
  `QObject.sender()`;
- when the sender is independently owned or longer-lived, `sender=` lets receiver
  destruction disconnect the otherwise dormant dispatcher;
- the method name is static and must remain valid for the receiver's lifetime.

Pass the sender whenever it is not in the receiver's QObject subtree. Omitting it can
leave safe no-op dispatchers attached to a long-lived sender even though the weak
receiver itself is gone. A direct bound-method connection is permitted only when the
receiver is deliberately process-lifetime, the retention is intentional and
documented, and the connection is not repeatedly recreated. Prefer weak dispatch for
dynamic or repeated connections regardless.

## 9. Timers

Every `QTimer` should have an intentional owner and stop policy.

For transient widgets:

- do not leave timers active after close;
- parent timers appropriately;
- stop them when their owning feature is destroyed if needed.

A timer connected to a bound method of a transient object can indirectly contribute to lifetime problems.

## 10. Event Filters

Whenever calling `installEventFilter(...)`, verify the corresponding lifetime relationship.

A long-lived filtered object can retain or invoke an event filter unexpectedly. Remove event filters explicitly when appropriate.

## 11. Long-lived Controllers Must Not Own Transient UI

Application-wide controllers/services should generally own state, orchestration, and reusable services.

They should generally not strongly own transient dialogs, temporary editors, page-local widgets, or short-lived message boxes.

UI objects may observe controller state. Controllers should not become accidental lifetime owners of transient UI.

## 12. Plugin and Registry Design

Plugin registries and capability registries should normally store:

- classes;
- factories;
- immutable metadata;
- configuration;
- descriptors.

Prefer not to store live `QWidget` or `QObject` instances unless the architecture explicitly requires persistent instances. Editor registries should generally register editor classes/factories rather than instantiated editors.

## 13. Dialog and Message-box Lifetime

Transient message boxes and confirmation dialogs require special care.

For modal dialogs using `exec()`, local ownership may be sufficient because execution blocks until completion.

For non-blocking dialogs using `.show()` or `.open()`:

- retain a strong reference while visible;
- release it at the lifecycle boundary appropriate to the dialog type.

Never rely on an unreferenced local variable for an asynchronous dialog. Also verify repeated dialog creation does not cause memory growth.

### `finished` is not native destruction

For a one-shot dialog using `WA_DeleteOnClose`, `finished` reports that the interaction
ended; it does not prove that Qt has destroyed the native object. Native deletion is
deferred. If an asynchronous registry releases the final Python reference at
`finished`, the wrapper can disappear before Qt completes deletion, or a stale wrapper
can survive after the native object is gone.

Use this sequence for transient delete-on-close dialogs:

1. create a unique opaque lifetime token;
2. insert `token -> dialog` into the open-dialog registry before calling `open()`;
3. allow `accept`, `reject`, or window close to emit `finished`;
4. keep the strong registry entry while `WA_DeleteOnClose` schedules native deletion;
5. observe `destroyed`;
6. remove the token on the next event-loop turn.

Callbacks that schedule registry cleanup must capture only the opaque token, never the
dialog. An identifier derived from `id(dialog)` is weaker because object IDs can be
reused. Operation-specific context may be released at `finished` after its callbacks
run, provided the lifetime registry still retains the dialog itself through
destruction.

Reusable dialogs follow a different policy. A reusable dialog is normally hidden at
`finished`, not deleted, so its temporary open-dialog registry entry may be released at
`finished` while its deliberate owner continues to retain it. Do not add
`WA_DeleteOnClose` merely to make cleanup uniform.

Furious implements these policies through `AppQDialog`, `AppQTransientDialog`, and
`AppQMessageBox`. Their asynchronous `open()` paths share the `AppQDialog` lifetime
registry; message-box presentation behavior must delegate ownership to that base path
rather than introduce a parallel registry.

## 14. Packaged and Compiled Builds Require Extra Caution

Object lifetime behavior that appears acceptable under native Python can expose problems more clearly in packaged or compiled builds.

When lifetime issues are suspected, test both where practical:

- native Python execution;
- the project's packaged/compiled executable.

Do not assume operating-system task-manager memory alone proves a leak. Distinguish between actual live-object growth, Python allocator high-water marks, Qt/native memory caching, and retained native resources.

The strongest evidence of a real leak is continued growth in live object/resource counts after repeated create/close cycles.

For Nuitka/PySide6 signal-retention work, include a compiled diagnostic that records
the size of Nuitka's `_protected` callback list before and after repeated cycles when
the compiled runtime exposes that internal diagnostic. It is not a production API and
may be hidden even though the post-import protection is active. Combine it with
`QObject.destroyed`, weak references, open-dialog registry size, operation-context
counts, and `shiboken6.isValid()` checks. Zero protected-list growth alone is not proof
of correct destruction, a missing counter is not zero growth, and stable process memory
alone is not proof of no leak.

## 15. Required Lifetime Review for UI Changes

Whenever a change creates or modifies dynamically managed Qt objects, explicitly review:

1. Who creates the object?
2. Who owns the Python reference?
3. Who is the `QObject` parent?
4. How long should it live?
5. How is it closed?
6. How is it destroyed?
7. Can any cache retain it?
8. Can any controller/registry retain it?
9. Does it have active timers?
10. Does it install event filters?
11. Does it connect to long-lived signals?
12. Can it disappear because the final Python reference is lost?

Do not consider the implementation complete until these questions have clear answers.

## 16. Lifetime Diagnostics

When investigating suspected lifetime issues, use targeted diagnostics where useful:

- `weakref.ref`;
- `weakref.finalize`;
- `QObject.destroyed`;
- live instance counters;
- `gc.get_referrers`;
- `gc.get_objects`;
- `tracemalloc`;
- repeated open/close stress tests.

Temporary diagnostics should be removed or minimized after the issue is understood. Do not keep large debug frameworks in production merely to compensate for unclear ownership.

## 17. Stress-test Transient UI

For reusable/transient UI infrastructure, prefer repeated lifecycle tests rather than testing only one open/close operation.

Representative procedure:

1. Record baseline live-object counts.
2. Open the dialog/editor.
3. Exercise `accept`, `reject`, and window-close paths where applicable.
4. Repeat 20–100 times.
5. Verify objects intended to die are destroyed.
6. Verify weak references clear.
7. Verify relevant pools/registries return to baseline.
8. Verify memory reaches a stable plateau rather than growing linearly.

For shared editor infrastructure, test multiple editor/dialog types rather than only one.

Run the same representative probe natively and as a standalone Nuitka build when the
code uses PySide6 signals or asynchronous transient dialogs. Vary protocol/editor order
so one family cannot hide a shared-registry or cached-callback defect. Required results
are:

- every expected `destroyed` signal fires;
- weak wrappers, open-dialog registries, and operation contexts return to zero;
- no wrapper becomes invalid before the close path completes;
- the registry still holds each transient dialog when `finished` is dispatched;
- Nuitka's protected callback collection has zero growth when observable; otherwise,
  the compiled probe has zero retained wrappers and the selected package configuration
  confirms that the dispatcher is not an eligible protected bound method;
- no per-cycle `gc.collect()` is needed to obtain those results.

## 18. Do Not Mask Lifetime Bugs

The following are not acceptable as standalone fixes:

- calling `gc.collect()` after every dialog closes;
- making every window global;
- retaining every created dialog forever;
- applying `WA_DeleteOnClose` indiscriminately;
- adding broad exception handlers around deleted-object errors;
- suppressing Qt warnings;
- hiding leaking widgets instead of destroying them.

Fix the ownership model instead.

## 19. Preserve PySide6 Wrapper Safety

Be careful about situations where the Python wrapper exists but the C++ `QObject` has already been deleted, or the C++ `QObject` survives while its Python wrapper is unexpectedly gone.

Avoid accessing objects after Qt destruction. Where needed:

- clear references on `destroyed`;
- avoid stale cached bound methods;
- avoid storing wrappers in long-lived registries.

## 20. Code Review Expectation

When reviewing existing code or implementing a refactor, treat lifetime correctness as part of normal code quality—not only something to inspect after a leak is reported.

If suspicious ownership is encountered while working on an unrelated feature, investigate and correct it when reasonably within scope. At minimum, do not introduce new lifetime ambiguity.

Reject a change when it:

- passes a transient or repeatedly created receiver's bound method directly to a
  PySide6 signal or `QTimer.singleShot()` in packaged-sensitive code;
- replaces that connection with a lambda/partial that strongly captures the receiver;
- omits `sender=` for `connectWeakly()` when an independently owned or longer-lived
  sender needs destroyed-receiver cleanup;
- releases a delete-on-close asynchronous dialog's final strong owner at `finished`;
- captures the transient dialog in a registry-cleanup callback;
- verifies only native CPython when the defect can be introduced by Nuitka's PySide6
  integration.

## Acceptance Criteria

For Qt/PySide6 UI code, a correct implementation should satisfy all applicable conditions:

- Transient windows/dialogs are destroyed when no longer needed.
- Reusable windows remain alive intentionally.
- Asynchronous top-level windows retain a valid Python reference while visible.
- Long-lived controllers do not accidentally retain transient widgets.
- Caches do not retain `QObject` instances unintentionally.
- Timers and event filters have clear lifecycle behavior.
- Custom close handlers preserve correct Qt lifecycle semantics.
- Repeated open/close cycles do not cause unbounded live-object growth.
- No visible window disappears because its wrapper is prematurely garbage-collected.
- Native Python execution remains correct.
- Packaged/compiled execution remains correct where testable.
- Transient/repeated PySide6 connections do not grow Nuitka's protected bound-method retention.
- Delete-on-close asynchronous dialogs remain retained through `finished` and are released only after `destroyed` dispatch.

**Final rule:** Every Qt object in this repository must have an intentional owner, lifetime, and destruction strategy. When in doubt, investigate the lifetime explicitly rather than relying on implicit Python garbage collection or Qt parent behavior.
