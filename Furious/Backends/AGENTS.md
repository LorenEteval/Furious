# Backend guidance

## Scope and extension

- A backend owns its protocol parsing/export, structured editors, runtime factory, validation, statistics, routing, and
  native-TUN behavior. Expose variation through plugin capabilities instead of shared-manager core-name branches.
- The full document submitted to the core is the runtime authority. Derive it from a copy and preserve the persisted
  profile plus unknown supported fields; fail visibly when a lossless representation is impossible.
- Runtime modules remain importable without constructing Qt editors. Registrations/imports must be literal enough for
  plugin discovery and Nuitka inclusion; factories create fresh widgets/runtimes and registries never retain them.

## Structured editors

- Loading is observational except for a documented compatibility normalization. Saving writes only represented fields
  that changed, preserves unknown siblings, and does not materialize absent effective defaults.
- Unknown future string values remain visible and survive an untouched round trip. A deliberate switch to a known
  tagged variant may replace only the incompatible variant data that control owns.

## Native TUN and runtime ownership

- Normal connection preparation operates on a runtime copy. With the backend native-TUN option enabled, generated TUN
  replaces runtime native TUN and suppresses application tun2socks. With it disabled, an existing user native TUN is
  preserved and also suppresses tun2socks. Without either, global TUN mode may use tun2socks.
- Proxy-only tests explicitly strip native TUN from their own copy. Never run two TUN implementations or silently turn
  malformed explicit TUN into another networking mode.
- A `CoreRuntime` owns exact resources, reports an actionable `startError()`, and has bounded, idempotent startup failure
  and shutdown cleanup. Process-backed implementations additionally reap their exact child.

## Verification

- Test mapping/URI round trips, malformed and unknown input, original-document immutability, runtime document equality,
  TUN matrices/proxy-only stripping, failed startup, and cleanup. Editor changes also require lifetime tests.
