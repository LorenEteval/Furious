# Furious package guidance

## Responsibility boundaries

- `Application` is the composition root. Elsewhere depend on the narrowest model, repository, service, controller, or
  plugin capability that owns the decision; do not add a second cache or state path to avoid an existing boundary.
- Domain shape, identity, and core-neutral transformations belong in `Models`; restoration, migration, ordering, and
  durable mutation in `Repository`; temporary work/external resources in `Service`; shared transitions in
  `Controllers`; backend variation in plugin contracts/implementations; host mutation in `Frozenlib` or a runtime;
  presentation in `Qt`, `Widget`, `Window`, or `Actions`.
- `Interface` and `Models` stay dependency-light and must not import UI, controllers, services, repositories, or concrete
  backends. Backend/runtime modules remain importable without constructing editors or the application.
- Package `__init__.py` files are curated compatibility surfaces, not mirrors. Import order can register settings or
  affect lazy plugin/Nuitka discovery; search public-import and packaging tests before changing exports.

## State, data, and ownership

- A `ServerProfile` keeps connection data separate from metadata such as display name, stable profile ID, subscription
  ownership, latency, and speed. Independent stored copies get new identity; runtime copies preserve identity while
  isolating mutable connection preparation.
- Profile ID, subscription source/key, connection fingerprint, display text, object identity, and row position are
  distinct. Pick the identity required by the operation and reject stale async work before write-back.
- Repository collections are live compatibility views owned once by `Storage`; do not wrap them in a competing
  authoritative collection. Prefer named repository mutations for new behavior so validation and commit points remain
  explicit.
- Process-lifetime global accessors expose deliberate application owners and can be unavailable during partial startup,
  isolated tests, or teardown. New code prefers explicit dependencies; compatibility callers tolerate absence rather
  than inventing fallback globals.
- Classify every Qt object as application-lifetime, reusable, or transient. Give it a durable Python owner, compatible
  QObject parent, and explicit reuse/destruction path. UI/lifetime work follows `Furious/Qt/AGENTS.md` even when the
  caller lives under `Widget`, `Window`, `Actions`, or a backend.

## Change routing

- Controllers publish shared state and coordinate owners; they do not own transient UI or long-running worker
  resources. Services do not create pages/message boxes. Widgets issue commands and present outcomes rather than
  absorbing workflow orchestration.
- Plugin registries own process-lifetime plugins, descriptors, and factories—not factory-created widgets, active
  runtimes, replies, or controller state. Bundled backends/extensions obey the same contracts as entry-point plugins.
- Keep GUI work bounded, cross worker results through the owning Qt thread, and define cancellation/supersession for
  every asynchronous workflow. Page visibility may control rendering, never ownership of collection or draining.
- Preserve unknown/forward-compatible fields through model, repository, backend editor, and serialization changes.
  Compatibility normalization must be narrow, intentional, and tested separately from observational loading.
- Import, clipboard, share-link, file, and QR paths reuse the owning plugin codecs and validation. QR is a presentation
  transport, not a second protocol parser; construct a complete neutral result before repository mutation and never log
  the secret-bearing payload.

## Local guides

- Read the applicable specialized guide for application composition, embedded core processes, platform helpers,
  repositories, plugins, services, backends, Qt ownership, translations, or bundled data. A missing child guide means
  this file and the root guide are sufficient; do not recreate one merely to restate them.
