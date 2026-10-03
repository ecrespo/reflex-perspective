# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (`0.x`: a breaking change bumps the minor).

## [0.2.0] - Unreleased

### Added

- `authorize=` hook on `perspective_api()`, `mount()`, `PerspectiveHub.asgi_app()` and
  `PerspectiveHub.serve()`: runs after the `Origin` check and before any Perspective
  session; a refusal code (4000–4999 or 1008) is delivered to the browser, a failing hook
  closes with 1011.
- `read_only=True`, `write_close_code=` (4409) and `read_variants=` on the same functions:
  only frames carrying exactly one known read request reach the engine.
- Public classifier: `request_variant()`, `is_read_request()`, `READ_VARIANTS`,
  `WRITE_VARIANT_NAMES`, `WRITE_CLOSE_CODE`.
- CI check that `PERSPECTIVE_VERSION` and the `perspective-python` pins match.
- Demo: access card on `/server` (authorize switch, counters, browser write) and
  `PERSPECTIVE_DEMO_READ_ONLY=1`.

### Changed

- Dependabot no longer proposes `perspective-python` upgrades; they follow
  `specs/runbooks/perspective-upgrade.md` together with the npm packages.

### Security

- The WebSocket endpoint can now authenticate connections and refuse every write from
  browsers. The read-only classifier is an allowlist per Perspective version that inspects
  every field of a frame, so a write appended to a read in the same frame is refused.
  Defaults are unchanged: enable both options in multi-user deployments.

## [0.1.0] - 2026-09-24

### Added

- `perspective_viewer` component: client-only, server-only and replicated modes,
  imperative actions, Custom Events as Reflex events, workspaces.
- `reflex_perspective.server`: `PerspectiveHub`, WebSocket endpoint with an `Origin`
  check, `perspective_api()`, `mount()`, `run_periodically()`.
- Demo app.

[0.2.0]: https://github.com/ecrespo/reflex-perspective/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ecrespo/reflex-perspective/releases/tag/v0.1.0
