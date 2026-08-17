# Backend and core-runtime guidance

These rules apply to bundled backend implementations and refine `Furious/AGENTS.md`.

## Configuration ownership

- The configuration passed to a core is authoritative. Preserve the persisted/original document and apply connection, routing, logging, statistics, and test preparation to a runtime/deep copy.
- Do not silently repair or delete explicit user core configuration and switch networking modes. Let the core or normal validation surface malformed user configuration.
- Protocol-specific parsing, editing, export, runtime construction, and compatibility belong to the backend/plugin capability, not shared connection UI or `ConnectionManager` conditionals.

## Native TUN contract

`KernelFactory.prepareTUN()` is the normal-connection ownership decision:

- Native-TUN option enabled: Furious-generated native TUN is authoritative in the runtime copy. Replace existing runtime native TUN, report handled, and do not start application tun2socks.
- If requested managed native TUN cannot be prepared safely, fail the connection with a useful error; never silently change to application tun2socks.
- Native-TUN option disabled with explicit user native TUN: preserve it unchanged, report handled (including malformed explicit values), and do not start application tun2socks.
- Native-TUN option disabled with no native TUN: do not inject native TUN; application tun2socks may be selected when global TUN mode requests it.
- Never allow backend native TUN and application tun2socks to run together.

Proxy-only operations such as download-speed tests must derive a separate configuration and explicitly strip/omit native TUN. Do not weaken normal-connection preservation to satisfy a probe/test workflow. Enabling the managed native-TUN option is the explicit user choice that permits replacement in the runtime copy; toggling it off never removes custom native TUN.

## Core lifecycle

- Factories return prepared kernel launches; process objects own only their exact child/process resources and callbacks.
- Startup failures must expose a useful start error and clean partially created resources. Shutdown must be bounded, reap exact owned children, release readers/queues/timers, and be idempotent.
- Do not use shell expansion for core commands. Do not log credentials, full arguments, secrets, or environment values.
- Keep lazy editor imports as literal imports inside factories/providers so Qt initialization stays lazy and Nuitka can discover dependencies.

## Required verification

- Run `tests.test_native_tun_semantics` after changing native-TUN preparation or application tun2socks selection.
- Test both persisted-document immutability and the exact runtime document submitted to the core.
- Test normal connection and proxy-only preparation independently; do not share a helper that erases their policy difference.
- For process changes, run the relevant external/process stress tests and verify failure cleanup.

## Code review rules

- Flag removal of custom native TUN while its backend-managed toggle is disabled.
- Flag a handled native-TUN path that can still instantiate application tun2socks.
- Flag test/probe TUN stripping implemented inside the normal connection policy.
- Flag unbounded process waits, orphaned reader threads/handles, or errors hidden behind a generic fallback.
