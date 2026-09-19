# Furious package guidance

Inherit repository-wide rules from the root `AGENTS.md`. This file preserves the package-level boundary between
domain, persistence, orchestration, platform integration, and presentation; nested guides specialize it in
place.

## Responsibility boundaries

- `Application` is the composition root. Elsewhere depend on the narrowest model, repository, service, controller, or
  plugin capability that owns the decision; do not add a second cache or state path to avoid an existing boundary.
- Domain shape, identity, and core-neutral transformations belong in `Models`; restoration, migration, ordering, and
  durable mutation in `Repository`; temporary work/external resources in `Service`; shared transitions in
  `Controllers`; backend variation in plugin contracts/implementations; host mutation in `Frozenlib` or a runtime;
  presentation in `Qt`, `Widget`, `Window`, or `Actions`.
- `Interface` and `Models` stay dependency-light and must not import UI, controllers, services, repositories, or concrete
  backends. Backend/runtime modules remain importable without constructing editors or the application.
- Package `__init__.py` files are curated compatibility surfaces, not mirrors. Import-time settings registration and
  lazy capability imports are distinct from application construction or plugin discovery. Preserve that distinction
  when changing exports; trace transitive imports and public-import/packaging tests, not just the edited module.

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
- UI/lifetime work consults `Furious/Qt/AGENTS.md` even from `Widget`, `Window`, `Actions`, or a backend; that sibling
  scope owns the shared presentation contract. A forwarding attribute or global accessor exposes an existing owner,
  not permission to construct a replacement service when the owner is absent.

## Change routing

- Controllers publish shared state and coordinate resource-owning services. New service APIs publish outcomes for UI
  consumers rather than create presentation. Existing update-service dialogs and settings/controller prompts are
  compatibility paths, not evidence of a strict UI-free service/controller layer; preserve callers until
  deliberately separating those responsibilities. Some shared managers are currently constructed under persistent
  widgets/pages. Construction location does not transfer workflow authority to every view: moving an owner must
  preserve one scheduler, result boundary, and cleanup path. Widgets should not absorb new workflow orchestration.
- Plugin registries index process-lifetime plugins, descriptors, and capabilities. Created editors and active
  runtimes transfer to explicit UI/workflow owners. A capability may own a reusable service, such as asset updating,
  but that service still needs a cleanup boundary. Built-ins use the public capability contract; existing
  global-access helpers are host integration, not an extra requirement for external plugins.
- Keep GUI work bounded, cross worker results through the owning Qt thread, and define cancellation/supersession for
  every asynchronous workflow. Page visibility may control rendering, never ownership of collection or draining.
- Preserve unknown/forward-compatible fields through model, repository, backend editor, and serialization changes.
  Compatibility normalization must be narrow, intentional, and tested separately from observational loading.
  A dict-like profile exposes its connection document through the mapping interface, not its complete persistence
  record. Choose the explicit profile, metadata, or connection representation required by each boundary; generic
  mapping conversion is not a profile backup.
- Import, clipboard, share-link, file, and QR paths reuse the owning plugin codecs and validation. QR is a presentation
  transport, not a second protocol parser. Decoding a transport envelope, validating a protocol, and committing a
  profile are separate boundaries: a recognized envelope is not permission to clear a group or import an unsupported
  protocol. Construct a complete valid result for each commit unit and never log the secret-bearing payload.

## Local guides

- Read the applicable specialized guide for application composition, embedded core processes, platform helpers,
  repositories, plugins, services, backends, Qt ownership, translations, or bundled data. A missing child guide means
  this file and the root guide are sufficient; do not recreate one merely to restate them. Existing child guides are
  established scopes: clarify inheritance or local invariants rather than deleting or consolidating them.
- `tests/test_public_api.py` and `tests/test_plugin_architecture.py` are starting points for import/export
  boundaries; consult the relevant behavior module in `tests/README.md` as well. Update this boundary map when
  ownership changes, without turning the present import graph into a ban on deliberate refactoring.
