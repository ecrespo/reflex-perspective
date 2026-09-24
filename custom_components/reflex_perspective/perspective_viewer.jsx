/**
 * reflex-perspective — React bridge between Reflex and Perspective's
 * `<perspective-viewer>` Custom Element.
 *
 * This module is shipped as a *shared asset* of the `reflex_perspective`
 * Python package and imported by the compiled Reflex page. It is responsible
 * for everything that cannot be expressed as plain props:
 *
 *   1. Bootstrapping Perspective's WebAssembly (client + server engines) once
 *      per page, lazily and only in the browser (SSR-safe).
 *   2. Building the data source for each viewer:
 *        - a WebWorker `Table` created from inline data / schema / URL, or
 *        - a remote `Table` served by `perspective-python` over a WebSocket
 *          (server-only "virtual" mode, or client/server "replicated" mode).
 *   3. Mapping declarative props (`config`, `workspace`, `theme`, ...) to the
 *      element's imperative `load()` / `restore()` / `restoreWorkspace()` API.
 *   4. Forwarding the element's Custom Events to Reflex event handlers.
 *   5. Exposing an imperative registry (`window.reflexPerspective`) so Python
 *      code can call `download()`, `save()`, `update()`... via `rx.call_function`.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import env from "$/env.json";
import { getBackendURL } from "$/utils/state";

/* -------------------------------------------------------------------------- */
/* Bootstrapping                                                              */
/* -------------------------------------------------------------------------- */

let BOOT = null;
let WORKER = null;
const WS_CLIENTS = new Map();

/**
 * Load and initialize Perspective exactly once. All imports are dynamic so the
 * module can be evaluated during server-side rendering without touching
 * `window`, `customElements` or `WebAssembly`.
 */
export function loadPerspective() {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Perspective can only run in a browser"));
  }
  if (BOOT === null) {
    BOOT = (async () => {
      const [clientMod, viewerMod, serverWasm, clientWasm] = await Promise.all([
        import("@perspective-dev/client"),
        import("@perspective-dev/viewer"),
        import("@perspective-dev/server/dist/wasm/perspective-server.wasm?url"),
        import("@perspective-dev/viewer/dist/wasm/perspective-viewer.wasm?url"),
        // Every bundled theme (+ icons and intl variables). Imported before the
        // first viewer upgrades so theme auto-detection sees all of them.
        import("@perspective-dev/viewer/dist/css/themes.css"),
      ]);
      const perspective = clientMod.default ?? clientMod;
      const viewer = viewerMod.default ?? viewerMod;
      await Promise.all([
        perspective.init_server(fetch(serverWasm.default)),
        viewer.init_client(fetch(clientWasm.default)),
      ]);
      // Plugins register themselves on import.
      await Promise.all([
        import("@perspective-dev/viewer-datagrid"),
        import("@perspective-dev/viewer-charts"),
      ]);
      await customElements.whenDefined("perspective-viewer");
      return perspective;
    })();
    BOOT.catch(() => {
      BOOT = null;
    });
  }
  return BOOT;
}

async function getWorker() {
  const perspective = await loadPerspective();
  if (WORKER === null) {
    WORKER = perspective.worker();
    WORKER.catch(() => {
      WORKER = null;
    });
  }
  return WORKER;
}

/**
 * Resolve a server URL. Absolute `ws://` / `wss://` URLs are used verbatim;
 * paths such as `/perspective` are resolved against the Reflex *backend*
 * (which may live on another port than the frontend during development).
 */
export function resolveServerUrl(url) {
  if (!url) return url;
  if (/^wss?:\/\//i.test(url)) return url;
  if (/^https?:\/\//i.test(url)) return url.replace(/^http/i, "ws");
  const endpoint = getBackendURL(env.EVENT);
  const path = url.startsWith("/") ? url : `/${url}`;
  endpoint.pathname = path;
  endpoint.search = "";
  endpoint.hash = "";
  return endpoint.toString();
}

function evictWebsocketClient(url) {
  WS_CLIENTS.delete(resolveServerUrl(url));
}

async function getWebsocketClient(url) {
  const resolved = resolveServerUrl(url);
  if (!WS_CLIENTS.has(resolved)) {
    const promise = (async () => {
      const perspective = await loadPerspective();
      const client = await perspective.websocket(resolved);
      try {
        await client.on_error(() => {
          // Evict so the next load() opens a fresh connection.
          if (WS_CLIENTS.get(resolved) === promise) WS_CLIENTS.delete(resolved);
          window.dispatchEvent(
            new CustomEvent("reflex-perspective-disconnect", {
              detail: { url: resolved },
            }),
          );
        });
      } catch (_) {
        /* older clients: no on_error */
      }
      return client;
    })();
    promise.catch(() => WS_CLIENTS.delete(resolved));
    WS_CLIENTS.set(resolved, promise);
  }
  return WS_CLIENTS.get(resolved);
}

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

const isNil = (x) => x === undefined || x === null;

/** JSON-safe deep copy (Dates -> ISO strings, drops functions/undefined). */
function plain(value) {
  if (value === undefined) return null;
  try {
    return JSON.parse(
      JSON.stringify(value, (_k, v) => (typeof v === "bigint" ? Number(v) : v)),
    );
  } catch (_) {
    return null;
  }
}

function stableKey(value) {
  try {
    return JSON.stringify(value ?? null);
  } catch (_) {
    return String(value);
  }
}

function errorMessage(err) {
  if (!err) return "Unknown error";
  if (typeof err === "string") return err;
  return err.message ?? String(err);
}

/** Resets used when a key disappears from a declarative config. */
const CONFIG_RESETS = {
  group_by: [],
  split_by: [],
  filter: [],
  sort: [],
  expressions: {},
  aggregates: {},
  plugin_config: null,
  columns_config: null,
  title: null,
  theme: null,
  settings: null,
  group_by_depth: null,
  plugin: null,
  windows: {},
};

const SHORTCUT_KEYS = [
  "plugin",
  "columns",
  "group_by",
  "split_by",
  "filter",
  "filter_op",
  "sort",
  "expressions",
  "aggregates",
  "group_by_depth",
  "group_rollup_mode",
  "split_rollup_mode",
  "plugin_config",
  "columns_config",
  "theme",
  "title",
  "settings",
];

/** Merge the `config` prop with the shortcut props (`plugin`, `group_by`, ...). */
function buildConfig(props) {
  const cfg = { ...(props.config ?? {}) };
  for (const key of SHORTCUT_KEYS) {
    const camel = key.replace(/_([a-z])/g, (_m, c) => c.toUpperCase());
    const value = props[camel] ?? props[key];
    if (!isNil(value)) cfg[key] = value;
  }
  if (!isNil(props.editMode)) {
    const plugin = cfg.plugin;
    if (isNil(plugin) || plugin === "Datagrid") {
      cfg.plugin_config = {
        ...(cfg.plugin_config ?? {}),
        edit_mode: props.editMode,
      };
    }
  }
  return cfg;
}

/** Compute the `restore()` payload to go from `prev` to `next`. */
function diffConfig(prev, next) {
  const out = { ...next };
  if (prev) {
    for (const key of Object.keys(prev)) {
      if (!(key in next) && key in CONFIG_RESETS) out[key] = CONFIG_RESETS[key];
    }
  }
  return out;
}

async function readUrl(url, format) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to fetch ${url}: ${resp.status}`);
  let fmt = format;
  if (!fmt) {
    const path = url.split("?")[0].toLowerCase();
    if (path.endsWith(".arrow") || path.endsWith(".feather")) fmt = "arrow";
    else if (path.endsWith(".csv") || path.endsWith(".tsv")) fmt = "csv";
    else if (path.endsWith(".ndjson") || path.endsWith(".jsonl"))
      fmt = "ndjson";
    else fmt = "json";
  }
  if (fmt === "arrow")
    return { data: await resp.arrayBuffer(), format: "arrow" };
  if (fmt === "csv") return { data: await resp.text(), format: "csv" };
  if (fmt === "ndjson") return { data: await resp.text(), format: "ndjson" };
  return { data: await resp.json(), format: "json" };
}

function tableOptions({ index, limit, name, format }) {
  const opts = {};
  if (!isNil(index) && index !== "") opts.index = index;
  if (!isNil(limit) && limit !== 0) opts.limit = limit;
  if (!isNil(name) && name !== "") opts.name = name;
  if (format === "ndjson") opts.format = "ndjson";
  return opts;
}

function toDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

let ANON = 0;

/* -------------------------------------------------------------------------- */
/* Imperative registry: window.reflexPerspective                              */
/* -------------------------------------------------------------------------- */

const REGISTRY = new Map(); // id -> { viewer, getTable, ready: Promise, resolve }

function slot(id) {
  if (!REGISTRY.has(id)) {
    let resolve;
    const ready = new Promise((r) => (resolve = r));
    REGISTRY.set(id, { viewer: null, table: null, ready, resolve });
  }
  return REGISTRY.get(id);
}

async function whenReady(id, timeoutMs = 15000) {
  const s = slot(id);
  if (s.viewer && s.table) return s;
  await Promise.race([
    s.ready,
    new Promise((_, rej) =>
      setTimeout(
        () => rej(new Error(`perspective viewer "${id}" is not ready`)),
        timeoutMs,
      ),
    ),
  ]);
  return slot(id);
}

function register(id, viewer, table) {
  const s = slot(id);
  s.viewer = viewer;
  s.table = table;
  s.resolve(s);
}

/** Mark a viewer's table as gone (reload in progress): callers wait again. */
function invalidate(id, viewer) {
  const s = REGISTRY.get(id);
  if (!s || s.viewer !== viewer || !s.table) return;
  s.table = null;
  s.ready = new Promise((r) => (s.resolve = r));
}

function unregister(id, viewer) {
  const s = REGISTRY.get(id);
  if (s && s.viewer === viewer) REGISTRY.delete(id);
}

const api = {
  /** Resolve once the viewer `id` has loaded its table. */
  whenReady,
  /** Raw access for advanced use: `{ viewer, table }`. */
  get: (id) => REGISTRY.get(id) ?? null,
  ids: () => [...REGISTRY.keys()],
  async save(id, options) {
    const { viewer } = await whenReady(id);
    return plain(await viewer.save(options ?? undefined));
  },
  async restore(id, config, options) {
    const { viewer } = await whenReady(id);
    await viewer.restore(config, options ?? undefined);
    return true;
  },
  async saveWorkspace(id, options) {
    const { viewer } = await whenReady(id);
    return plain(await viewer.saveWorkspace(options ?? undefined));
  },
  async restoreWorkspace(id, config) {
    const { viewer } = await whenReady(id);
    await viewer.restoreWorkspace(config);
    return true;
  },
  async reset(id, all = false) {
    const { viewer } = await whenReady(id);
    await viewer.reset(!!all);
    return true;
  },
  async toggleConfig(id, force) {
    const { viewer } = await whenReady(id);
    await viewer.toggleConfig(isNil(force) ? undefined : !!force);
    return true;
  },
  async download(id, method = "csv") {
    const { viewer } = await whenReady(id);
    await viewer.download({ method });
    return true;
  },
  async copy(id, method = "csv") {
    const { viewer } = await whenReady(id);
    await viewer.copy({ method });
    return true;
  },
  /**
   * Export the view. Text methods (csv/json/ndjson/html/json-config) return
   * text; binary ones (arrow*, plugin PNG) return a base64 `data:` URL.
   */
  async export(id, method = "csv") {
    const { viewer } = await whenReady(id);
    const out = await viewer.export({ method });
    if (typeof out === "string") return out;
    if (out instanceof Blob) {
      if (out.type.startsWith("text/") || out.type.includes("json"))
        return await out.text();
      return await toDataUrl(out);
    }
    if (out instanceof ArrayBuffer || ArrayBuffer.isView(out))
      return await toDataUrl(
        new Blob([out], { type: "application/vnd.apache.arrow.file" }),
      );
    return JSON.stringify(plain(out), null, 2);
  },
  /** Stream rows into the viewer's table without going through state. */
  async update(id, rows, options) {
    const { table } = await whenReady(id);
    await table.update(rows, options ?? undefined);
    return true;
  },
  async remove(id, keys) {
    const { table } = await whenReady(id);
    await table.remove(keys);
    return true;
  },
  async replace(id, data) {
    const { table } = await whenReady(id);
    await table.replace(data);
    return true;
  },
  async clear(id) {
    const { table } = await whenReady(id);
    await table.clear();
    return true;
  },
  async size(id) {
    const { table } = await whenReady(id);
    return await table.size();
  },
  async schema(id) {
    const { table } = await whenReady(id);
    return plain(await table.schema());
  },
  async addPanel(id, config) {
    const { viewer } = await whenReady(id);
    return await viewer.addPanel(config);
  },
  async resize(id) {
    const { viewer } = await whenReady(id);
    await viewer.resize();
    return true;
  },
  async themes(id) {
    const { viewer } = await whenReady(id);
    return plain(await viewer.getThemes());
  },
};

if (typeof window !== "undefined") {
  window.reflexPerspective = Object.assign(
    window.reflexPerspective ?? {},
    api,
    {
      loadPerspective,
      resolveServerUrl,
    },
  );
}

/* -------------------------------------------------------------------------- */
/* The React component                                                        */
/* -------------------------------------------------------------------------- */

/**
 * Zero-specificity defaults so any Reflex style prop (emitted as an emotion
 * class) or inline style wins over them.
 */
function ensureDefaultStyles() {
  if (typeof document === "undefined") return;
  if (document.getElementById("reflex-perspective-defaults")) return;
  const tag = document.createElement("style");
  tag.id = "reflex-perspective-defaults";
  tag.textContent =
    ":where(perspective-viewer[data-reflex-perspective]){display:block;position:relative;width:100%;height:600px;}";
  document.head.appendChild(tag);
}

/** DOM event props that Reflex's base component triggers compile to. */
const DOM_EVENT_PROPS = new Set([
  "onBlur",
  "onFocus",
  "onDoubleClick",
  "onContextMenu",
  "onMouseDown",
  "onMouseEnter",
  "onMouseLeave",
  "onMouseMove",
  "onMouseOut",
  "onMouseOver",
  "onMouseUp",
  "onScroll",
  "onScrollEnd",
]);

export function ReflexPerspectiveViewer(props) {
  const {
    id,
    className,
    style,
    data,
    schema,
    index,
    limit,
    tableName,
    url,
    urlFormat,
    serverUrl,
    serverTable,
    serverMode,
    workspace,
    updateRows,
    removeKeys,
    autoSize,
    autoPause,
    throttle,
    pluginLimits,
  } = props;

  const elRef = useRef(null);
  const [booted, setBooted] = useState(false);
  const [loadTick, setLoadTick] = useState(0);
  const [retryTick, setRetryTick] = useState(0);
  const retryAttempts = useRef(0);
  const retryTimer = useRef(null);
  const scheduleRetry = useCallback(() => {
    if (retryTimer.current) return;
    const delay = Math.min(
      10000,
      500 * 2 ** Math.min(retryAttempts.current, 5),
    );
    retryAttempts.current += 1;
    retryTimer.current = setTimeout(() => {
      retryTimer.current = null;
      setRetryTick((t) => t + 1);
    }, delay);
  }, []);
  useEffect(
    () => () => retryTimer.current && clearTimeout(retryTimer.current),
    [],
  );

  // Latest props / callbacks, readable from async code without re-running effects.
  const propsRef = useRef(props);
  propsRef.current = props;

  const idRef = useRef(null);
  if (idRef.current === null)
    idRef.current = id || `reflex-perspective-${++ANON}`;
  const viewerId = id || idRef.current;
  const viewerIdRef = useRef(viewerId);
  viewerIdRef.current = viewerId;

  // Serialized queue of imperative operations on the element.
  const queue = useRef(Promise.resolve());
  const enqueue = useCallback((fn) => {
    const next = queue.current.then(fn).catch((err) => {
      reportError(err);
    });
    queue.current = next;
    return next;
  }, []);

  const loaded = useRef(null); // { table, owned: [..], data, updateRows, removeKeys }
  const appliedConfig = useRef(null); // last config object applied via restore()
  const appliedConfigKey = useRef(null);
  const appliedWorkspaceKey = useRef(null);
  const emittedConfigKey = useRef(null); // last config sent to on_config_update

  function reportError(err) {
    const msg = errorMessage(err);
    console.error("[reflex-perspective]", msg, err);
    propsRef.current.onError?.(msg);
  }

  /* ------------------------------ boot ----------------------------------- */
  useEffect(() => {
    ensureDefaultStyles();
    let alive = true;
    loadPerspective()
      .then(() => alive && setBooted(true))
      .catch((err) => alive && reportError(err));
    return () => {
      alive = false;
    };
  }, []);

  /* ----------------------- render policy + limits ------------------------ */
  useEffect(() => {
    const el = elRef.current;
    if (!booted || !el) return;
    if (!isNil(autoSize)) el.setAutoSize?.(!!autoSize);
    if (!isNil(autoPause)) el.setAutoPause?.(!!autoPause);
    if (!isNil(throttle)) el.setThrottle?.(throttle);
  }, [booted, autoSize, autoPause, throttle]);

  const pluginLimitsKey = stableKey(pluginLimits);
  useEffect(() => {
    if (!booted || !pluginLimits) return;
    for (const [name, limits] of Object.entries(pluginLimits)) {
      try {
        const plugin = elRef.current?.getPlugin?.(name);
        if (!plugin) continue;
        if (!isNil(limits?.max_cells)) plugin.max_cells = limits.max_cells;
        if (!isNil(limits?.max_columns))
          plugin.max_columns = limits.max_columns;
      } catch (err) {
        reportError(err);
      }
    }
  }, [booted, pluginLimitsKey]);

  /* ------------------------------ events --------------------------------- */
  useEffect(() => {
    const el = elRef.current;
    if (!booted || !el) return;
    const ctl = new AbortController();
    const on = (name, fn) =>
      el.addEventListener(name, fn, { signal: ctl.signal });

    on("perspective-config-update", async (e) => {
      const cb = propsRef.current.onConfigUpdate;
      if (!cb) return;
      let cfg = null;
      try {
        cfg = e?.detail?.getConfig
          ? await e.detail.getConfig()
          : await el.save();
      } catch (_) {
        try {
          cfg = await el.save();
        } catch (err) {
          return;
        }
      }
      cfg = plain(cfg);
      const key = stableKey(cfg);
      if (key === emittedConfigKey.current) return;
      emittedConfigKey.current = key;
      cb(cfg);
    });
    on("perspective-click", (e) => {
      const d = e.detail ?? {};
      propsRef.current.onClick?.(
        plain({
          row: d.row ?? {},
          column_names: d.column_names ?? [],
          config: d.config ?? {},
          panel: d.panel ?? null,
        }),
      );
    });
    on("perspective-select", (e) => {
      const d = e.detail ?? {};
      let insert = [];
      let remove = [];
      try {
        insert = d.insertFilters ?? [];
        remove = d.removeFilters ?? [];
      } catch (_) {
        /* ignore */
      }
      propsRef.current.onSelect?.(
        plain({
          selected: d.selected ?? false,
          row: d.row ?? {},
          column_names: d.column_names ?? [],
          insert_filters: insert,
          remove_filters: remove,
          panel: d.panel ?? null,
        }),
      );
    });
    on("perspective-global-filter-update", (e) => {
      propsRef.current.onGlobalFilterUpdate?.(plain(e.detail ?? []));
    });
    on("perspective-layout-update", (e) => {
      propsRef.current.onLayoutUpdate?.(plain(e.detail?.panels ?? []));
    });
    on("perspective-active-panel-update", (e) => {
      propsRef.current.onActivePanelUpdate?.(e.detail?.panel ?? null);
    });
    on("perspective-toggle-settings", (e) => {
      propsRef.current.onToggleSettings?.(!!e.detail);
    });
    return () => ctl.abort();
  }, [booted]);

  /* --------------------- data source: build + load ----------------------- */
  const schemaKey = stableKey(schema);
  useEffect(() => {
    const el = elRef.current;
    if (!booted || !el) return;
    let cancelled = false;
    const owned = [];

    enqueue(async () => {
      if (cancelled) return;
      const p = propsRef.current;
      // How far a server-mode load got: "connect" (opening the socket),
      // "open" (finding the hosted table) or "render" (restoring config).
      let stage = "connect";
      try {
        const name = p.tableName || undefined;
        let table = null;
        let client = null;
        let source = "data";

        if (p.serverUrl) {
          source = p.serverMode === "replicated" ? "replicated" : "server";
          client = await getWebsocketClient(p.serverUrl);
          stage = "open";
          let remoteName = p.serverTable;
          if (!remoteName) {
            const names = await client.get_hosted_table_names();
            remoteName = names?.[0];
            if (!remoteName)
              throw new Error("The Perspective server hosts no tables");
          }
          const remote = await client.open_table(remoteName);
          stage = "render";
          if (source === "replicated") {
            const worker = await getWorker();
            const view = await remote.view();
            owned.push(view);
            let remoteIndex = null;
            try {
              remoteIndex = await remote.get_index();
            } catch (_) {
              /* no index */
            }
            table = await worker.table(
              view,
              tableOptions({
                index: remoteIndex,
                name: name ?? `${remoteName}-replica-${++ANON}`,
              }),
            );
            owned.unshift(table);
            client = worker; // the replica lives in the local worker
          } else {
            table = remote;
          }
        } else {
          const worker = await getWorker();
          let payload = p.data;
          let format = null;
          if (p.url && isNil(payload)) {
            const res = await readUrl(p.url, p.urlFormat);
            payload = res.data;
            format = res.format;
          }
          const opts = tableOptions({
            index: p.index,
            limit: p.limit,
            name: name ?? viewerId,
            format,
          });
          if (p.schema && Object.keys(p.schema).length > 0) {
            // `format` describes the payload, not the schema object.
            const { format: _fmt, ...schemaOpts } = opts;
            table = await worker.table(p.schema, schemaOpts);
            if (
              !isNil(payload) &&
              !(Array.isArray(payload) && payload.length === 0)
            ) {
              await table.update(payload, format ? { format } : undefined);
            }
          } else {
            table = await worker.table(isNil(payload) ? [] : payload, opts);
          }
          owned.unshift(table);
          client = worker;
        }

        if (cancelled) {
          for (const o of owned) o.delete?.({ lazy: true })?.catch?.(() => {});
          return;
        }

        // Modern binding: load the Client, then select the table by name in
        // the same restore() so the viewer renders exactly once.
        const tname = await table.get_name();
        const tclient = client ?? (await table.get_client());
        await el.load(tclient);

        const cfg = buildConfig(p);
        appliedConfig.current = null;
        appliedConfigKey.current = null;
        const ws = p.workspace;
        if (ws && Object.keys(ws).length > 0) {
          const panels = {};
          for (const [pid, pcfg] of Object.entries(ws.panels ?? {})) {
            panels[pid] = { table: tname, ...(pcfg ?? {}) };
          }
          await el.restoreWorkspace(ws.panels ? { ...ws, panels } : ws);
          appliedWorkspaceKey.current = stableKey(ws);
          if (Object.keys(cfg).length > 0) await el.restore(cfg);
        } else {
          await el.restore({ ...cfg, table: tname });
        }
        appliedConfig.current = cfg;
        appliedConfigKey.current = stableKey(cfg);

        loaded.current = {
          table,
          tableName: tname,
          owned,
          data: p.data,
          updateRows: p.updateRows,
          removeKeys: p.removeKeys,
        };
        register(viewerId, el, table);
        setLoadTick((t) => t + 1);

        if (p.onLoad) {
          let info = { table: null, schema: {}, num_rows: 0, source };
          try {
            info = {
              table: await table.get_name(),
              schema: plain(await table.schema()),
              num_rows: await table.size(),
              source,
            };
          } catch (_) {
            /* best effort */
          }
          p.onLoad(info);
        }
        retryAttempts.current = 0;
      } catch (err) {
        for (const o of owned) {
          try {
            await o.delete?.({ lazy: true });
          } catch (_) {
            /* ignore */
          }
        }
        owned.length = 0;
        if (cancelled) return;
        // Config errors (bad column names, ...) will not fix themselves.
        if (!p.serverUrl || stage === "render") throw err;
        // Server modes: the backend may be restarting ("connect") or still
        // building its tables ("open"). Only a failed connection is dropped
        // from the cache; a live socket is reused by the retry.
        if (stage === "connect") evictWebsocketClient(p.serverUrl);
        reportError(err);
        scheduleRetry();
      }
    });

    return () => {
      cancelled = true;
      enqueue(async () => {
        const cur = loaded.current;
        loaded.current = null;
        invalidate(viewerId, el);
        try {
          await el.eject?.();
        } catch (_) {
          /* element may be gone */
        }
        for (const o of cur?.owned ?? owned) {
          try {
            await o.delete?.({ lazy: true });
          } catch (_) {
            /* already deleted */
          }
        }
      });
    };
  }, [
    booted,
    schemaKey,
    index,
    limit,
    tableName,
    url,
    urlFormat,
    serverUrl,
    serverTable,
    serverMode,
    retryTick,
  ]);

  /* ---------------------- reconnect (server modes) ----------------------- */
  useEffect(() => {
    if (!serverUrl || typeof window === "undefined") return;
    const resolved = resolveServerUrl(serverUrl);
    const handler = (e) => {
      if (e.detail?.url !== resolved) return;
      propsRef.current.onDisconnect?.(resolved);
      scheduleRetry();
    };
    window.addEventListener("reflex-perspective-disconnect", handler);
    return () => {
      window.removeEventListener("reflex-perspective-disconnect", handler);
    };
  }, [serverUrl]);

  /* ----------------------- data prop -> replace() ------------------------ */
  useEffect(() => {
    const cur = loaded.current;
    if (!cur || serverUrl || cur.data === data) return;
    cur.data = data;
    enqueue(async () => {
      if (isNil(data)) await cur.table.clear();
      else await cur.table.replace(data);
    });
  }, [data, loadTick]);

  /* ------------------ streaming props -> update()/remove() --------------- */
  useEffect(() => {
    const cur = loaded.current;
    if (!cur || cur.updateRows === updateRows) return;
    cur.updateRows = updateRows;
    if (isNil(updateRows)) return;
    if (Array.isArray(updateRows) && updateRows.length === 0) return;
    enqueue(() => cur.table.update(updateRows));
  }, [updateRows, loadTick]);

  useEffect(() => {
    const cur = loaded.current;
    if (!cur || cur.removeKeys === removeKeys) return;
    cur.removeKeys = removeKeys;
    if (!Array.isArray(removeKeys) || removeKeys.length === 0) return;
    enqueue(() => cur.table.remove(removeKeys));
  }, [removeKeys, loadTick]);

  /* ------------------------ config -> restore() -------------------------- */
  const config = buildConfig(props);
  const configKey = stableKey(config);
  useEffect(() => {
    if (!loaded.current) return;
    if (configKey === appliedConfigKey.current) return;
    // Controlled-component loop guard: the viewer already has this config.
    if (configKey === emittedConfigKey.current) {
      appliedConfig.current = config;
      appliedConfigKey.current = configKey;
      return;
    }
    const el = elRef.current;
    const prev = appliedConfig.current;
    appliedConfig.current = config;
    appliedConfigKey.current = configKey;
    enqueue(() => el.restore(diffConfig(prev, config)));
  }, [configKey, loadTick]);

  const workspaceKey = stableKey(workspace);
  useEffect(() => {
    if (!loaded.current || !workspace) return;
    if (workspaceKey === appliedWorkspaceKey.current) return;
    appliedWorkspaceKey.current = workspaceKey;
    const el = elRef.current;
    const tname = loaded.current.tableName;
    const panels = workspace.panels
      ? Object.fromEntries(
          Object.entries(workspace.panels).map(([k, v]) => [
            k,
            { table: tname, ...(v ?? {}) },
          ]),
        )
      : undefined;
    enqueue(() =>
      el.restoreWorkspace(panels ? { ...workspace, panels } : workspace),
    );
  }, [workspaceKey, loadTick]);

  /* ------------------------------ unmount -------------------------------- */
  useEffect(() => {
    const el = elRef.current;
    return () => {
      unregister(viewerIdRef.current, el);
      // Free the element's WASM resources once pending work has settled.
      // `delete()` is irreversible: any later call on the element throws
      // "null pointer passed to rust". React StrictMode (on in Reflex dev
      // mode) simulates unmount + remount on the *same* DOM node, so only
      // delete once the element has really left the document.
      queue.current.then(async () => {
        if (!el || el.isConnected) return;
        try {
          await el.delete?.();
        } catch (_) {
          /* ignore */
        }
      });
    };
  }, []);

  // Forward Reflex's standard DOM triggers (on_focus, on_mouse_*, ...),
  // `custom_attrs` and `ref`. Perspective's own callbacks (onClick,
  // onSelect, ...) are wired to Custom Events above and never forwarded.
  const passthrough = {};
  for (const [key, value] of Object.entries(props)) {
    if (DOM_EVENT_PROPS.has(key) || /^(data|aria)-/.test(key))
      passthrough[key] = value;
  }
  const userRef = props.ref;
  const setRef = useCallback(
    (node) => {
      elRef.current = node;
      if (typeof userRef === "function") userRef(node);
      else if (userRef) userRef.current = node;
    },
    [userRef],
  );

  return (
    <perspective-viewer
      {...passthrough}
      ref={setRef}
      id={id}
      className={className}
      style={style}
      data-reflex-perspective=""
    />
  );
}

export default ReflexPerspectiveViewer;
