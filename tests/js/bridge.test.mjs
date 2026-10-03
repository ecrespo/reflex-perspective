// Unit tests for the pure helpers of perspective_viewer.jsx (node --test).
// tests/test_bridge_js.py bundles the bridge with esbuild and passes its path.
import assert from "node:assert/strict";
import { test } from "node:test";

const bridge = await import(process.env.BRIDGE_BUNDLE);

test("resolveServerUrl resolves paths against the Reflex backend", () => {
  assert.equal(
    bridge.resolveServerUrl("/perspective"),
    "ws://localhost:8000/perspective",
  );
  assert.equal(bridge.resolveServerUrl("wss://x.test/p"), "wss://x.test/p");
  assert.equal(bridge.resolveServerUrl("https://x.test/p"), "wss://x.test/p");
});

// REQ-VIEW-011: close codes reach the bridge only as the text of the error the
// official transport passes to Client.on_error ("WebSocket closed <code>").
test("closeCodeFromError reads the code from errors and strings", () => {
  assert.equal(bridge.closeCodeFromError(new Error("WebSocket closed 4409")), 4409);
  assert.equal(bridge.closeCodeFromError("ClientError: WebSocket closed 4401"), 4401);
  assert.equal(bridge.closeCodeFromError({ message: "WebSocket closed 1006" }), 1006);
});

test("closeCodeFromError returns null without a close code", () => {
  for (const value of [
    new Error("WebSocket transport error (3)"),
    "Generic Websocket Error",
    "WebSocket closed",
    "WebSocket closed 12345",
    null,
    undefined,
  ]) {
    assert.equal(bridge.closeCodeFromError(value), null, String(value));
  }
});

test("isPermanentRefusal: 4400-4499 except 4429", () => {
  for (const code of [4400, 4401, 4403, 4409, 4499]) {
    assert.equal(bridge.isPermanentRefusal(code), true, String(code));
  }
  for (const code of [4429, 4399, 4500, 1000, 1006, 1008, 1011, null, undefined]) {
    assert.equal(bridge.isPermanentRefusal(code), false, String(code));
  }
});

test("refusalMessage names the code, the URL and the likely cause", () => {
  const url = "ws://localhost:8000/perspective";
  const ro = bridge.refusalMessage(4409, url);
  assert.match(ro, /4409/);
  assert.match(ro, /perspective/);
  assert.match(ro, /read-only/i);
  assert.match(ro, /edit_mode/);
  assert.match(bridge.refusalMessage(4401, url), /authenticat/i);
  assert.match(bridge.refusalMessage(4403, url), /forbidden|permission/i);
  assert.match(bridge.refusalMessage(4499, url), /4499/);
});

// REQ-VIEW-011: a permanent refusal blocks retries for its URL and warns once.
test("noteClose records permanent refusals and warns once per URL", () => {
  const url = "ws://localhost:8000/refused";
  const warnings = [];
  const warn = (msg) => warnings.push(msg);
  assert.equal(bridge.isRefused(url), false);
  assert.equal(bridge.noteClose(url, new Error("WebSocket closed 4403"), warn), 4403);
  assert.equal(bridge.isRefused(url), true);
  assert.equal(bridge.noteClose(url, "WebSocket closed 4403", warn), 4403);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /4403/);
});

test("noteClose keeps retrying transient closes", () => {
  const warnings = [];
  const warn = (msg) => warnings.push(msg);
  for (const [i, error] of [
    "WebSocket closed 4429",
    "WebSocket closed 1006",
    "WebSocket transport error (3)",
  ].entries()) {
    const url = `ws://localhost:8000/transient-${i}`;
    bridge.noteClose(url, error, warn);
    assert.equal(bridge.isRefused(url), false, error);
  }
  assert.equal(warnings.length, 0);
  assert.equal(bridge.noteClose("ws://x/y", "WebSocket closed 1006", warn), 1006);
  assert.equal(bridge.noteClose("ws://x/y", "boom", warn), null);
});
