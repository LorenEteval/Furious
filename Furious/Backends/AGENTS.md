# Backend guidance

Inherit `Furious/AGENTS.md` and its root ancestor. Consult Plugins/Models/Service for the contracts consumed by
this scope. This scope adds rules shared by all bundled proxy backends without making the richest backend the
generic default.

## Common backend contract

- A backend supplies the subset of protocol, editor, execution, routing, TUN, statistics, settings, action, and
  asset capabilities it actually supports. Shared code dispatches capabilities; a built-in backend with no
  statistics, URI export, or download-test implementation remains valid.
- The complete persisted core document is authoritative. Prepare logging, routing, endpoints, probes, and TUN on an
  independent runtime copy; failed preparation must not mutate the stored profile.
- Structured editors are partial projections. Loading is observational except for a narrow documented migration;
  untouched save preserves unknown fields/values and absent defaults. Editing one represented leaf preserves unknown
  siblings and unrelated branches. URI export represents the codec's supported projection, not a lossless backup
  of every document field; exporting must leave the source document unchanged.
- Malformed external input returns controlled validation with backend context. Do not create a plausible but different
  profile, and do not log credentials, complete URIs, or documents. Keep parsing, editor acceptance, and runtime
  validation distinct: a tolerant loader preserves a document for correction without promising it can execute.
- Configuration/runtime modules stay importable without constructing Qt editors. Plugin registration remains explicit
  enough for compiled discovery. An editor factory returns a fresh projection, not a repository commit: the caller
  owns the editable snapshot, acceptance validation, identity resolution, and eventual write-back. Runtime factories
  likewise transfer fresh execution resources to the workflow owner. Editor acceptance and runtime readiness are
  different validations; neither may silently rewrite stored data to make a later stage succeed.
- `Furious/Plugins/Runtime.py` checks that serialization yields nonempty text and carries structured diagnostics on failure;
  it does not parse pre-serialized strings or validate a backend's complete schema. Keep serialization success,
  backend configuration acceptance, execution start, and readiness as separate evidence.

## TUN and runtime policy

- Global TUN asks the selected runtime factory about native ownership and application tun2socks. For backends
  exposing native TUN, managed mode replaces that backend's TUN projection on the runtime copy; disabled management
  preserves explicit user TUN, even malformed for runtime rejection. External Core instead declares host-tun2socks
  opt-in; do not infer its executable's private document format or impose Xray/Hysteria2-native rules on it.
- Supported proxy/download-test preparation explicitly strips native TUN from the copied document. The generic
  `proxyModeOnly` request does not sanitize arbitrary plugin configuration by itself. Required managed-native-TUN
  rejection raises `TUNPreparationError`; do not silently switch implementations.
- A runtime owns its exact process/thread/readers/monitors and publishes an actionable start error. Stop/dispose
  must be bounded, idempotent, and safe after partial acquisition. Report incomplete reaping explicitly; reaching a
  deadline or changing logical execution state does not prove that native resources have exited.
- Runtime factories follow the current plugin contract: fully prepare and return one owned launch whose zero-argument
  start is separate from readiness observation. If preparation fails before a valid launch transfers to the caller,
  the factory must release its own partial resources; the caller cannot dispose a runtime it never received. Do not
  hide readiness waits, Boolean success channels, or controller policy inside a backend runtime.

## Backend scopes

- Read the selected backend's nested guide before changing its configuration, editor, protocol codec, runtime, TUN,
  routing, asset, statistics, or process behavior. Those child guides own backend-specific compatibility details; keep
  this parent focused on rules that every backend must satisfy.
- Check a shared backend-contract change against Xray, Hysteria 1, Hysteria 2, and External Core, including an absent
  optional capability and a present capability that cannot perform the requested operation. Those are different
  outcomes; neither permits shared code to substitute another backend's policy.

## Verification

- Test mapping/document/URI round trips; malformed, legacy, and unknown input; untouched-editor preservation;
  persisted immutability; exact runtime/probe documents; every native/application-TUN case;
  startup/rollback/cleanup; assets and statistics where applicable; plugin discovery; and repeated editor/dialog
  destruction. Start with `tests/test_backend_editor_contract.py`, `tests/test_native_tun_semantics.py`, and
  `tests/test_plugin_architecture.py`. Revalidate these shared rules against a minimally capable backend whenever a
  capability changes.
