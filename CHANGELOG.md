# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (`0.x`: a breaking change bumps the minor).

## [0.3.0] - 2026-10-03

### Added

- `max_sessions=` on `serve()`, `asgi_app()`, `perspective_api()` and `mount()`: once the hub
  has that many sessions open, new sockets are refused with 4429 (after `authorize`).
- `on_reject=` hook called with the close code of every refusal (1008, `authorize`'s code, 1011,
  4409, 4429), sync or async; its errors are logged and never change the close.
- `PerspectiveHub.session_count`.
- Demo: `PERSPECTIVE_DEMO_MAX_SESSIONS`; refusals counted with `on_reject`.
- `on_disconnect` receives `(url, code)` with the WebSocket close code (`None` if unknown);
  one-argument handlers keep receiving the URL.

### Changed

- Server viewers no longer reconnect after a permanent refusal (close codes 4400–4499 except
  4429, e.g. 4401/4403 from `authorize` or 4409 from `read_only`); the browser console explains
  the code once per URL. Reload the page to reconnect.

## [0.2.0] - 2026-10-03

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

[0.3.0]: https://github.com/ecrespo/reflex-perspective/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ecrespo/reflex-perspective/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ecrespo/reflex-perspective/releases/tag/v0.1.0
