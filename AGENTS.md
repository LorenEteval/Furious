# Qt/PySide6 Object Lifetime Guidelines

## Purpose

This file defines repository-level guidance for coding agents working on this project.

For long-running Qt/PySide6 applications, **object lifetime management is a critical correctness requirement**.

Any change involving `QObject`, `QWidget`, `QDialog`, `QAction`, `QMenu`, `QTimer`, signals/slots, controllers,
registries, caches, or dynamically created UI objects must be reviewed for lifetime behavior.

Treat memory leaks, stale object retention, dangling Qt wrappers, and premature garbage collection as serious bugs.

---

# 1. Core Lifetime Principle

Every `QObject`-derived object should have an intentional owner, lifetime, and destruction strategy.

For each dynamically created object, determine which category it belongs to.

## Long-lived objects

Examples:

* main windows
* persistent pages/views
* application-wide controllers
* shared managers/services

These are expected to live for most or all of the process lifetime.

They may have stable ownership through:

* application globals
* a long-lived parent `QObject`
* a controller/service owner

Do not repeatedly recreate long-lived objects unnecessarily.

## Reusable windows/dialogs

These may be opened and closed multiple times while intentionally reusing the same instance.

They require:

* an explicit strong Python owner
* a clear hide/show lifecycle
* reset/update logic when reopened

Do not accidentally destroy a reusable dialog after every close.

Do not keep multiple duplicate instances if only one is intended.

## Transient windows/dialogs

These should be created for one interaction and destroyed afterward.

Examples may include:

* temporary editors
* confirmation dialogs
* information dialogs
* one-shot configuration dialogs

Transient objects should not remain strongly referenced after closing.

Where appropriate:

* use `WA_DeleteOnClose`
* call the correct base close implementation
* remove owning references after destruction
* stop timers and remove event filters
* ensure long-lived services do not retain callbacks to them

Do not blindly apply `WA_DeleteOnClose` to every dialog. Use it only when the intended lifecycle is truly transient.

---

# 2. Prevent Memory Leaks

When modifying or adding Qt UI code, always consider whether the object can remain alive after it should have been
destroyed.

Pay special attention to strong references created by:

* module-level lists, dicts, and sets
* application globals
* controllers
* plugin/capability registries
* factories
* object pools
* translation registries
* signal/slot connections
* event filters
* timers
* `QAction` and `QMenu` ownership
* closures
* bound methods
* partial functions
* lambda captures
* caches

A closed dialog should not remain reachable indefinitely unless reuse is intentional.

---

# 3. Be Extremely Careful With Caches

Do not use unbounded caches on instance methods of transient UI objects.

A dangerous example:

```
class Editor:
    @functools.lru_cache(None)
    def groupBoxSequence(self):
        ...
```

The cache key contains `self`, which can retain the entire editor instance and its Qt child tree indefinitely.

For transient `QWidget` / `QDialog` / `QObject` instances, prefer:

* normal instance attributes
* immutable cached metadata
* class-level/static caches that do not contain live instances
* weak-reference-based structures where appropriate

Before adding:

* `@lru_cache`
* `@cache`
* module-level caches

verify that no transient `QObject` instance can become part of a cache key or cached value.

---

# 4. Weak References Are Not a Universal Fix

When using `weakref`, verify that:

* weak-reference callbacks do not capture the object strongly
* bound methods do not accidentally keep the instance alive
* dead weak references are cleaned up
* iteration over weak pools handles destroyed objects safely
* another unrelated container is not still holding a strong reference

A weak-reference registry cannot fix a leak if another object still owns the widget strongly.

---

# 5. Prevent Premature Garbage Collection

Lifetime bugs can happen in the opposite direction as well.

Never assume that calling `.show()` automatically gives a top-level window a safe Python lifetime.

Dangerous example:

```
def show_editor(self):
    editor = ServerEditor()
    editor.show()
```

After `show_editor()` returns, the local variable may be the final Python reference.

Depending on Qt/PySide6 ownership semantics, the wrapper may then be garbage-collected and the window may:

* immediately disappear
* be destroyed unexpectedly
* behave inconsistently
* cause wrapper/native-object errors later

For non-modal top-level widgets/windows, ensure a durable owner exists.

Suitable strategies include:

* storing the window as an instance attribute
* maintaining a managed collection of open windows
* assigning an appropriate `QObject` parent
* removing stored references when the object emits `destroyed`
* using `exec()` for genuinely modal dialogs

Do not make every window global merely to solve this problem.

Choose ownership according to the intended lifecycle.

---

# 6. Qt Parent Ownership Must Be Intentional

Qt parent/child ownership is not equivalent to application lifecycle correctness.

A transient dialog parented to a long-lived widget may remain alive even after being closed.

For every dynamically created widget, ask:

* Who is the `QObject` parent?
* How long does the parent live?
* Does closing destroy the child or only hide it?
* Should the child survive for reuse?
* Does Python also retain a reference?

Do not automatically parent every transient dialog to a main window or another application-lifetime widget.

---

# 7. Closing Is Not Always Destruction

Calling `.close()` does not necessarily mean an object is destroyed.

Review behavior involving:

* `closeEvent`
* `accept`
* `reject`
* `done`
* `hide`
* `deleteLater`
* `WA_DeleteOnClose`

Custom lifecycle overrides must call their base implementation when required.

For example, an incorrect `closeEvent` override can suppress normal `QDialog` lifecycle signals such as:

* `finished`
* `accepted`
* `rejected`

Do not silently replace Qt lifecycle behavior unless intentional.

---

# 8. Signals and Slots

Signals/slots can create subtle lifetime relationships.

When a transient widget connects to a long-lived object, review whether that connection affects lifetime or can invoke a
destroyed receiver.

Examples of long-lived senders include:

* controllers
* shared managers/services
* application globals
* plugin managers
* persistent timers

Use Qt's automatic `QObject` disconnection where sufficient.

When it is not sufficient:

* disconnect explicitly
* remove callbacks
* stop timers
* remove event filters
* use weak-reference-safe callback patterns

Avoid unnecessary manual disconnect boilerplate when Qt already manages the connection safely.

---

# 9. Timers

Every `QTimer` should have an intentional owner and stop policy.

For transient widgets:

* do not leave timers active after close
* parent timers appropriately
* stop them when their owning feature is destroyed if needed

A timer connected to a bound method of a transient object can indirectly contribute to lifetime problems.

---

# 10. Event Filters

Whenever calling:

```
installEventFilter(...)
```

verify the corresponding lifetime relationship.

A long-lived filtered object can retain or invoke an event filter unexpectedly.

Remove event filters explicitly when appropriate.

---

# 11. Long-lived Controllers Must Not Own Transient UI

Application-wide controllers/services should generally own:

* state
* orchestration
* reusable services

They should generally NOT strongly own:

* transient dialogs
* temporary editors
* page-local widgets
* short-lived message boxes

UI objects may observe controller state.

Controllers should not become accidental lifetime owners of transient UI.

---

# 12. Plugin and Registry Design

Plugin registries and capability registries should normally store:

* classes
* factories
* immutable metadata
* configuration
* descriptors

Prefer not to store live `QWidget` / `QObject` instances unless the architecture explicitly requires persistent
instances.

Editor registries should generally register editor classes/factories rather than instantiated editors.

---

# 13. Dialog and Message-box Lifetime

Transient message boxes and confirmation dialogs require special care.

For modal dialogs using `exec()`:

* local ownership may be sufficient because execution blocks until completion

For non-blocking dialogs using `.show()` or `.open()`:

* retain a strong reference while visible
* release it intentionally when destroyed

Never rely on an unreferenced local variable for an asynchronous dialog.

Also verify repeated dialog creation does not cause memory growth.

---

# 14. Packaged/Compiled Builds Require Extra Caution

Object lifetime behavior that appears acceptable under native Python can expose problems more clearly in packaged or
compiled builds.

When lifetime issues are suspected, test both where practical:

* native Python execution
* the project's packaged/compiled executable

Do not assume operating-system task-manager memory alone proves a leak.

Distinguish between:

* actual live-object growth
* Python allocator high-water marks
* Qt/native memory caching
* retained native resources

The strongest evidence of a real leak is continued growth in live object/resource counts after repeated create/close
cycles.

---

# 15. Required Lifetime Review for UI Changes

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

---

# 16. Lifetime Diagnostics

When investigating suspected lifetime issues, use targeted diagnostics where useful.

Useful tools include:

* `weakref.ref`
* `weakref.finalize`
* `QObject.destroyed`
* live instance counters
* `gc.get_referrers`
* `gc.get_objects`
* `tracemalloc`
* repeated open/close stress tests

Temporary diagnostics should be removed or minimized after the issue is understood.

Do not keep large debug frameworks in production merely to compensate for unclear ownership.

---

# 17. Stress-test Transient UI

For reusable/transient UI infrastructure, prefer repeated lifecycle tests rather than testing only one open/close
operation.

Representative procedure:

1. Record baseline live-object counts.
2. Open the dialog/editor.
3. Close it.
4. Repeat 20–50 times.
5. Verify objects intended to die are destroyed.
6. Verify weak references clear.
7. Verify relevant pools/registries return to baseline.
8. Verify memory reaches a stable plateau rather than growing linearly.

For shared editor infrastructure, test multiple editor/dialog types rather than only one.

---

# 18. Do Not Mask Lifetime Bugs

The following are not acceptable as standalone fixes:

* calling `gc.collect()` after every dialog closes
* making every window global
* retaining every created dialog forever
* applying `WA_DeleteOnClose` indiscriminately
* adding broad exception handlers around destroyed-object errors
* suppressing Qt warnings
* hiding leaking widgets instead of destroying them

Fix the ownership model instead.

---

# 19. Preserve PySide6 Wrapper Safety

Be careful about situations where:

* the Python wrapper exists but the C++ `QObject` has already been deleted
* the C++ `QObject` survives while its Python wrapper is unexpectedly gone

Avoid accessing objects after Qt destruction.

Where needed:

* clear references on `destroyed`
* avoid stale cached bound methods
* avoid storing wrappers in long-lived registries

---

# 20. Code Review Expectation

When reviewing existing code or implementing a refactor, treat lifetime correctness as part of normal code quality—not
only something to inspect after a leak is reported.

If suspicious ownership is encountered while working on an unrelated feature, investigate and correct it when reasonably
within scope.

At minimum, do not introduce new lifetime ambiguity.

---

# Acceptance Criteria

For Qt/PySide6 UI code, a correct implementation should satisfy all applicable conditions:

* Transient windows/dialogs are destroyed when no longer needed.
* Reusable windows remain alive intentionally.
* Asynchronous top-level windows retain a valid Python reference while visible.
* Long-lived controllers do not accidentally retain transient widgets.
* Caches do not retain `QObject` instances unintentionally.
* Timers and event filters have clear lifecycle behavior.
* Custom close handlers preserve correct Qt lifecycle semantics.
* Repeated open/close cycles do not cause unbounded live-object growth.
* No visible window disappears because its wrapper is prematurely garbage-collected.
* Native Python execution remains correct.
* Packaged/compiled execution remains correct where testable.

## Final Rule

**Every Qt object in this repository must have an intentional owner, lifetime, and destruction strategy.**

When in doubt, investigate the lifetime explicitly rather than relying on implicit Python garbage collection or Qt
parent behavior.
