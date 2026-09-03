import { reactive } from "vue";
import { api, engineRows, schemaFields, isSecretField } from "./api";

const THEME_KEY = "aidb-theme";

const HOST_KEYS = ["host", "hostname", "server", "addr", "address"];
const PORT_KEYS = ["port"];
const DB_KEYS = ["dbname", "database", "db", "schema", "catalog", "sid", "service_name"];

export const state = reactive({
  dark: localStorage.getItem(THEME_KEY) === "dark",
  view: "home",
  engines: [],
  gallery: [],
  connections: [],
  selectedId: null,
  pingStatus: {},
  sourcePatched: {},
  labels: { namespace: "命名空间", collection: "集合", field: "字段" },
  overlayKind: "source",
  overlayNs: null,
  overlayColl: null,
  columns: [],
  fieldPatched: {},
  overlayPatched: false,
  sourceOverlay: { description: "", query_rules: "" },
  collectionOverlay: { description: "", fields: {} },
  versions: [],
  histView: "",
  treeMsg: "请选择数据源",
  treeNodes: [],
  treeCursor: null,
  catalogQ: "",
  selectedNodeKey: "",
  focusField: "",
  connForm: { id: "", name: "", engine: null, config: {} },
  drawerShow: false,
  drawerMode: "create",
  drawerStep: "gallery",
});

export function setDark(value) {
  state.dark = !!value;
  localStorage.setItem(THEME_KEY, state.dark ? "dark" : "light");
}

export function engineById(id) {
  const fromEngines = state.engines.find((e) => e.id === id);
  if (fromEngines) return fromEngines;
  const fromGallery = state.gallery.find((e) => e.id === id);
  if (!fromGallery) return null;
  return {
    id: fromGallery.id,
    family: fromGallery.family,
    aliases: fromGallery.aliases || [],
    form_schema: fromGallery.form_schema,
    labels: fromGallery.labels,
    icon: fromGallery.icon || "",
    ui: fromGallery.ui || {
      visible: fromGallery.visible !== false,
      label: fromGallery.label || fromGallery.id,
      icon: fromGallery.icon || "",
      description: fromGallery.description || "",
    },
    label: fromGallery.label || fromGallery.id,
  };
}

export function engineLabel(engineId) {
  if (!engineId) return "";
  const g = state.gallery.find((e) => e.id === engineId);
  if (g && (g.label || g.id)) return g.label || g.id;
  const e = engineById(engineId);
  if (!e) return engineId;
  if (e.ui && e.ui.label) return e.ui.label;
  if (e.label) return e.label;
  return e.id || engineId;
}

export function applyEngineLabels(engine) {
  if (!engine || !engine.labels) return;
  state.labels = {
    namespace: engine.labels.namespace || state.labels.namespace,
    collection: engine.labels.collection || state.labels.collection,
    field: engine.labels.field || state.labels.field,
  };
}

export function applyCatalogLabels(labels) {
  if (!labels) return;
  state.labels = {
    namespace: labels.namespace_label || state.labels.namespace,
    collection: labels.collection_label || state.labels.collection,
    field: labels.field_label || state.labels.field,
  };
}

function pickConfigValue(config, candidates) {
  const cfg = config && typeof config === "object" ? config : {};
  const keys = Object.keys(cfg);
  for (const want of candidates) {
    const wantLc = String(want).toLowerCase();
    for (const k of keys) {
      if (String(k).toLowerCase() !== wantLc) continue;
      const raw = cfg[k];
      if (raw == null || raw === "") continue;
      const text = String(raw).trim();
      if (text) return text;
    }
  }
  return "";
}

/** 通用摘要：host:port / db，不按引擎名分支。 */
export function connectionSummary(config) {
  const host = pickConfigValue(config, HOST_KEYS);
  const port = pickConfigValue(config, PORT_KEYS);
  const db = pickConfigValue(config, DB_KEYS);
  const hostPort = host ? (port ? host + ":" + port : host) : port;
  if (hostPort && db) return hostPort + " / " + db;
  return hostPort || db || "";
}

export async function loadEngines() {
  const data = await api("/api/engines");
  state.engines = engineRows(data);
}

export async function loadGallery() {
  const data = await api("/api/engines/gallery");
  const rows = engineRows(data);
  rows.sort((a, b) => {
    const av = a.visible === false ? 1 : 0;
    const bv = b.visible === false ? 1 : 0;
    if (av !== bv) return av - bv;
    return String(a.label || a.id).localeCompare(String(b.label || b.id), "zh");
  });
  state.gallery = rows;
}

export function engineIconPath(engineId) {
  if (!engineId) return "";
  const g = state.gallery.find((e) => e.id === engineId);
  if (g && g.icon) return g.icon;
  const e = state.engines.find((row) => row.id === engineId);
  if (e && e.ui && e.ui.icon) return e.ui.icon;
  return "";
}

export function rebuildForm(engineId, config) {
  const eng = engineById(engineId);
  applyEngineLabels(eng);
  state.connForm.engine = engineId || null;
  const values = config || {};
  const next = {};
  for (const field of schemaFields(eng)) {
    if (isSecretField(field)) {
      next[field.key] = "";
      continue;
    }
    const raw = values[field.key];
    if (raw != null && raw !== "***") {
      next[field.key] = field.type === "int" ? Number(raw) : String(raw);
    } else if (field.default != null) {
      next[field.key] = field.type === "int" ? Number(field.default) : field.default;
    } else {
      next[field.key] = field.type === "int" ? null : "";
    }
  }
  state.connForm.config = next;
}

export function readEngineConfig() {
  const eng = engineById(state.connForm.engine);
  const config = {};
  for (const field of schemaFields(eng)) {
    const val = state.connForm.config[field.key];
    if (isSecretField(field) && (val == null || val === "")) continue;
    if (field.type === "int") {
      config[field.key] = val === "" || val == null ? null : Number(val);
    } else {
      config[field.key] = val;
    }
  }
  return config;
}

export function fillConnectionForm(conn) {
  if (!conn) {
    state.connForm.id = "";
    state.connForm.name = "";
    state.connForm.engine = null;
    state.connForm.config = {};
    return;
  }
  state.connForm.id = conn.id;
  state.connForm.name = conn.name || "";
  rebuildForm(conn.engine, conn.config || {});
}

export async function refreshSourcePatched() {
  const next = { ...state.sourcePatched };
  await Promise.all(
    (state.connections || []).map(async (conn) => {
      try {
        const data = await api("/api/sources/" + encodeURIComponent(conn.id) + "/overlay");
        next[conn.id] = !!data.patched;
      } catch {
        next[conn.id] = false;
      }
    })
  );
  state.sourcePatched = next;
}

export async function refreshConnections() {
  const data = await api("/api/connections");
  state.connections = Array.isArray(data) ? data : data.connections || [];
  await refreshSourcePatched();
}

export function pingOf(id) {
  return state.pingStatus[id] || "unknown";
}

export async function pingConnection(id) {
  if (!id) return false;
  try {
    await api("/api/connections/" + encodeURIComponent(id) + "/ping", { method: "POST" });
    state.pingStatus = { ...state.pingStatus, [id]: "ok" };
    return true;
  } catch (err) {
    state.pingStatus = { ...state.pingStatus, [id]: "fail" };
    throw err;
  }
}

export function goHome() {
  state.view = "home";
  state.selectedId = null;
  state.treeNodes = [];
  state.treeCursor = null;
  state.treeMsg = "请选择数据源";
  state.versions = [];
  state.histView = "";
  state.selectedNodeKey = "";
  state.focusField = "";
  state.overlayKind = "source";
  state.overlayNs = null;
  state.overlayColl = null;
}

export async function selectConnection(id) {
  state.selectedId = id;
  const conn = state.connections.find((c) => c.id === id);
  fillConnectionForm(conn);
  state.overlayKind = "source";
  state.overlayNs = null;
  state.overlayColl = null;
  state.focusField = "";
  await loadSourceOverlay();
  await loadCatalogRoot();
  await loadHistory();
}

export async function openDetail(id) {
  state.view = "detail";
  await selectConnection(id);
}

export function openCreateDrawer() {
  fillConnectionForm(null);
  state.drawerMode = "create";
  state.drawerStep = "gallery";
  state.drawerShow = true;
}

export function openEditDrawer(conn) {
  const row = conn || state.connections.find((c) => c.id === state.selectedId);
  fillConnectionForm(row);
  state.drawerMode = "edit";
  state.drawerStep = "form";
  state.drawerShow = true;
}

export function pickGalleryEngine(item) {
  if (!item || item.visible === false) return false;
  state.connForm.id = "";
  state.connForm.name = "";
  rebuildForm(item.id);
  state.drawerStep = "form";
  return true;
}

export function closeDrawer() {
  state.drawerShow = false;
}

export async function loadCatalog(params) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") usp.set(k, v);
  }
  return api("/api/catalog?" + usp.toString());
}

function itemToNode(item) {
  if (item.collection) {
    return {
      key: "coll:" + (item.namespace || "") + "/" + item.collection,
      kind: "collection",
      namespace: item.namespace || "",
      collection: item.collection,
      name: item.collection,
      kindLabel: state.labels.collection || "集合",
      label: item.collection,
      patched: !!item.patched,
      open: false,
      children: [],
      loaded: false,
      loading: false,
      cursor: null,
      expandable: true,
    };
  }
  if (item.namespace) {
    return {
      key: "ns:" + item.namespace,
      kind: "namespace",
      namespace: item.namespace,
      collection: null,
      name: item.namespace,
      kindLabel: state.labels.namespace || "命名空间",
      label: item.namespace,
      patched: false,
      open: false,
      children: [],
      loaded: false,
      loading: false,
      cursor: null,
      expandable: true,
    };
  }
  return null;
}

function appendItems(parent, page) {
  const items = page.items || [];
  for (const item of items) {
    const node = itemToNode(item);
    if (node) parent.children.push(node);
  }
  parent.cursor = page.next_cursor || null;
}

export async function loadCatalogRoot() {
  state.treeNodes = [];
  state.treeCursor = null;
  if (!state.selectedId) {
    state.treeMsg = "请选择数据源";
    return;
  }
  state.treeMsg = "加载中…";
  try {
    const page = await loadCatalog({
      source_id: state.selectedId,
      q: state.catalogQ || undefined,
      limit: 50,
    });
    applyCatalogLabels(page.labels);
    // 已进入某一数据源详情，目录从 namespace 起，不再套一层 source
    const items = page.items || [];
    state.treeNodes = [];
    for (const item of items) {
      const node = itemToNode(item);
      if (node) state.treeNodes.push(node);
    }
    state.treeCursor = page.next_cursor || null;
    state.treeMsg = state.treeNodes.length ? "" : "暂无命名空间";
    if (state.overlayKind === "source") {
      state.selectedNodeKey = "source";
    }
  } catch (err) {
    state.treeMsg = err.message || "加载失败";
  }
}

export async function loadMoreRoot() {
  if (!state.treeCursor || !state.selectedId) return;
  const page = await loadCatalog({
    source_id: state.selectedId,
    q: state.catalogQ || undefined,
    cursor: state.treeCursor,
    limit: 50,
  });
  for (const item of page.items || []) {
    const node = itemToNode(item);
    if (node) state.treeNodes.push(node);
  }
  state.treeCursor = page.next_cursor || null;
}

export async function expandNode(node) {
  if (!node || node.loading) return;
  if (node.kind === "field") return;
  if (node.open) {
    node.open = false;
    return;
  }
  node.open = true;
  if (node.loaded) return;
  await loadNodeChildren(node);
}

export async function loadNodeChildren(node) {
  if (!state.selectedId || !node) return;
  node.loading = true;
  try {
    if (node.kind === "namespace") {
      const page = await loadCatalog({
        source_id: state.selectedId,
        namespace: node.namespace,
        q: state.catalogQ || undefined,
        limit: 50,
      });
      applyCatalogLabels(page.labels);
      node.children = [];
      appendItems(node, page);
      node.loaded = true;
    } else if (node.kind === "collection") {
      const page = await loadCatalog({
        source_id: state.selectedId,
        namespace: node.namespace,
        collection: node.collection,
        limit: 50,
      });
      applyCatalogLabels(page.labels);
      const item = (page.items && page.items[0]) || {};
      state.columns = page.columns || item.columns || [];
      const overlayFields = (page.overlays && page.overlays.fields) || {};
      const fp = item.field_patched || {};
      node.children = [];
      for (const col of state.columns) {
        const patched = !!(fp[col.name] || overlayFields[col.name]);
        node.children.push({
          key: "field:" + node.namespace + "/" + node.collection + "/" + col.name,
          kind: "field",
          namespace: node.namespace,
          collection: node.collection,
          name: col.name,
          type: col.type || "",
          comment: col.comment || "",
          kindLabel: state.labels.field || "字段",
          label: col.name,
          patched,
          open: false,
          children: [],
          loaded: true,
          expandable: false,
        });
      }
      node.loaded = true;
      node.cursor = page.next_cursor || null;
    }
  } finally {
    node.loading = false;
  }
}

export async function loadMore(node) {
  if (!node || !node.cursor || !state.selectedId) return;
  node.loading = true;
  try {
    const params = { source_id: state.selectedId, cursor: node.cursor, limit: 50 };
    if (node.kind === "namespace") params.namespace = node.namespace;
    if (state.catalogQ) params.q = state.catalogQ;
    const page = await loadCatalog(params);
    appendItems(node, page);
  } finally {
    node.loading = false;
  }
}

export function isNodeActive(node) {
  if (!node) return false;
  if (state.selectedNodeKey) return node.key === state.selectedNodeKey;
  if (node.kind === "collection") {
    return (
      state.overlayKind === "collection" &&
      state.overlayNs === node.namespace &&
      state.overlayColl === node.collection
    );
  }
  return false;
}

export function isSourceOverlayActive() {
  return state.overlayKind === "source" && state.selectedNodeKey === "source";
}

export async function activateSourceOverlay() {
  state.selectedNodeKey = "source";
  state.focusField = "";
  state.overlayKind = "source";
  state.overlayNs = null;
  state.overlayColl = null;
  await loadSourceOverlay();
  await loadHistory();
}

export async function activateNode(node) {
  if (!node) return;
  state.selectedNodeKey = node.key;
  state.focusField = node.kind === "field" ? node.name : "";
  if (node.kind === "namespace") {
    if (!node.open && !node.loaded) {
      node.open = true;
      await loadNodeChildren(node);
    }
    return;
  }
  if (node.kind === "collection") {
    state.overlayKind = "collection";
    state.overlayNs = node.namespace;
    state.overlayColl = node.collection;
    if (!node.open) {
      node.open = true;
    }
    if (!node.loaded) await loadNodeChildren(node);
    const page = await loadCatalog({
      source_id: state.selectedId,
      namespace: node.namespace,
      collection: node.collection,
      limit: 50,
    });
    const item = (page.items && page.items[0]) || {};
    state.columns = page.columns || item.columns || [];
    await loadCollectionOverlay();
    await loadHistory();
    return;
  }
  if (node.kind === "field") {
    state.overlayKind = "collection";
    state.overlayNs = node.namespace;
    state.overlayColl = node.collection;
    await loadCollectionOverlay();
    await loadHistory();
  }
}

export function overlayCollectionPath() {
  return (
    "/api/sources/" +
    encodeURIComponent(state.selectedId) +
    "/namespaces/" +
    encodeURIComponent(state.overlayNs) +
    "/collections/" +
    encodeURIComponent(state.overlayColl) +
    "/overlay"
  );
}

export function overlayBase() {
  if (state.overlayKind === "collection" && state.overlayNs && state.overlayColl) {
    return overlayCollectionPath();
  }
  return "/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay";
}

export async function loadSourceOverlay() {
  if (!state.selectedId) return;
  const data = await api("/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay");
  const body = data.body || {};
  state.sourceOverlay = {
    description: body.description || "",
    query_rules: body.query_rules || "",
  };
  state.overlayPatched = !!data.patched;
  state.sourcePatched = { ...state.sourcePatched, [state.selectedId]: !!data.patched };
}

export async function loadCollectionOverlay() {
  if (!state.selectedId || !state.overlayNs || !state.overlayColl) return;
  const data = await api(overlayCollectionPath());
  const body = data.body || {};
  const fields = { ...(body.fields || {}) };
  const names = new Set([...Object.keys(fields), ...state.columns.map((c) => c.name)]);
  const next = {};
  for (const name of names) next[name] = fields[name] || "";
  state.collectionOverlay = { description: body.description || "", fields: next };
  state.overlayPatched = !!data.patched;
  const fp = {};
  for (const [k, v] of Object.entries(fields)) {
    if (v) fp[k] = true;
  }
  state.fieldPatched = fp;
}

export async function saveOverlay() {
  if (!state.selectedId) return;
  if (state.overlayKind === "collection") {
    const fields = {};
    for (const [name, text] of Object.entries(state.collectionOverlay.fields || {})) {
      const t = (text || "").trim();
      if (t) fields[name] = t;
    }
    await api(overlayCollectionPath(), {
      method: "PUT",
      body: { description: state.collectionOverlay.description, fields },
    });
    await loadCollectionOverlay();
  } else {
    await api("/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay", {
      method: "PUT",
      body: {
        description: state.sourceOverlay.description,
        query_rules: state.sourceOverlay.query_rules,
      },
    });
    await loadSourceOverlay();
  }
  await loadCatalogRoot();
  await loadHistory();
}

export async function loadHistory() {
  state.histView = "";
  state.versions = [];
  if (!state.selectedId) return;
  const data = await api(overlayBase() + "/versions");
  const versions = Array.isArray(data) ? data : data.versions || [];
  state.versions = versions;
}

export async function viewVersion(ver) {
  const data = await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id));
  state.histView = JSON.stringify(data.body || data, null, 2);
}

export async function diffVersion(ver) {
  const toId = (state.versions[0] && state.versions[0].id) || ver.id;
  const data = await api(
    overlayBase() +
      "/diff?from=" +
      encodeURIComponent(ver.id) +
      "&to=" +
      encodeURIComponent(toId)
  );
  state.histView = data.diff || data || "";
}

export async function restoreVersion(ver) {
  await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id) + "/restore", {
    method: "POST",
  });
  if (state.overlayKind === "collection") await loadCollectionOverlay();
  else await loadSourceOverlay();
  await loadHistory();
  await loadCatalogRoot();
}

export async function nameVersion(ver, label) {
  await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id) + "/name", {
    method: "POST",
    body: { label },
  });
  await loadHistory();
}

export async function exportBundle(includeHistory) {
  return api("/api/export", { method: "POST", body: { include_history: !!includeHistory } });
}

export async function importBundle(obj) {
  await api("/api/import", { method: "POST", body: obj });
  await refreshConnections();
}
