/* AIDB 配置台：引擎表单只来自 GET /api/engines 的 form_schema。 */
(() => {
  const state = {
    engines: [],
    connections: [],
    selectedId: null,
    labels: { namespace: "命名空间", collection: "集合", field: "字段" },
    tree: null,
    overlayKind: "source", // source | collection
    overlayNs: null,
    overlayColl: null,
    columns: [],
    versions: [],
    headMeta: null,
  };

  const $ = (id) => document.getElementById(id);

  async function api(path, opts = {}) {
    const headers = { Accept: "application/json", ...(opts.headers || {}) };
    let body = opts.body;
    if (body && typeof body === "object" && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const res = await fetch(path, { ...opts, headers, body });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const msg =
        (data && (data.message || data.detail || data.code)) ||
        res.statusText ||
        "请求失败";
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.payload = data;
      throw err;
    }
    return data;
  }

  function setMsg(id, text, kind) {
    const el = $(id);
    if (!el) return;
    el.textContent = text || "";
    el.className = "msg" + (kind ? " " + kind : "");
  }

  function engineById(id) {
    return state.engines.find((e) => e.id === id) || null;
  }

  function applyLabels(engine) {
    if (!engine || !engine.labels) return;
    state.labels = {
      namespace: engine.labels.namespace || "命名空间",
      collection: engine.labels.collection || "集合",
      field: engine.labels.field || "字段",
    };
  }

  function fieldsOf(engine) {
    if (!engine) return [];
    const schema = engine.form_schema || {};
    return Array.isArray(schema.fields) ? schema.fields : [];
  }

  function renderEngineSelect() {
    const sel = $("engine-select");
    sel.innerHTML = "";
    for (const eng of state.engines) {
      const opt = document.createElement("option");
      opt.value = eng.id;
      opt.textContent = eng.id + (eng.family ? " · " + eng.family : "");
      sel.appendChild(opt);
    }
    renderEngineFields();
  }

  function renderEngineFields(config) {
    const eng = engineById($("engine-select").value);
    applyLabels(eng);
    const box = $("engine-fields");
    box.innerHTML = "";
    const values = config || {};
    for (const field of fieldsOf(eng)) {
      const label = document.createElement("label");
      label.textContent = field.label || field.key;
      const input = document.createElement(
        field.type === "text" ? "textarea" : "input"
      );
      input.dataset.key = field.key;
      if (field.type === "int") input.type = "number";
      else if (field.type === "password" || field.secret) input.type = "password";
      else if (field.type !== "text") input.type = "text";
      input.required = !!field.required && field.type !== "password" && !field.secret;
      if (field.type === "password" || field.secret) {
        input.placeholder = "留空则保持不变";
        input.autocomplete = "new-password";
      } else if (field.default != null && values[field.key] == null) {
        input.value = field.default;
      }
      if (values[field.key] != null && values[field.key] !== "***") {
        input.value = values[field.key];
      }
      label.appendChild(input);
      box.appendChild(label);
    }
  }

  function readEngineConfig() {
    const config = {};
    for (const input of $("engine-fields").querySelectorAll("[data-key]")) {
      const key = input.dataset.key;
      if (input.type === "password" && !input.value) continue;
      if (input.type === "number") {
        config[key] = input.value === "" ? null : Number(input.value);
      } else {
        config[key] = input.value;
      }
    }
    return config;
  }

  function renderConnections() {
    const ul = $("conn-list");
    ul.innerHTML = "";
    for (const conn of state.connections) {
      const li = document.createElement("li");
      if (conn.id === state.selectedId) li.classList.add("active");
      const title = document.createElement("span");
      title.textContent = conn.name || conn.id;
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = conn.engine || "";
      li.append(title, meta);
      li.addEventListener("click", () => selectConnection(conn.id));
      ul.appendChild(li);
    }
  }

  function fillConnectionForm(conn) {
    $("conn-id").value = conn ? conn.id : "";
    $("conn-name").value = conn ? conn.name : "";
    if (conn && conn.engine) {
      $("engine-select").value = conn.engine;
    }
    renderEngineFields(conn ? conn.config : {});
  }

  async function refreshConnections() {
    const data = await api("/api/connections");
    state.connections = Array.isArray(data) ? data : data.connections || [];
    renderConnections();
  }

  async function selectConnection(id) {
    state.selectedId = id;
    const conn = state.connections.find((c) => c.id === id);
    fillConnectionForm(conn);
    renderConnections();
    state.overlayKind = "source";
    state.overlayNs = null;
    state.overlayColl = null;
    await loadSourceOverlay();
    await loadCatalogRoot();
    await loadHistory();
  }

  async function loadCatalog(params) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") usp.set(k, v);
    }
    return api("/api/catalog?" + usp.toString());
  }

  function patchedBadge(flag) {
    if (!flag) return "";
    const span = document.createElement("span");
    span.className = "badge";
    span.textContent = "已修";
    return span;
  }

  async function loadCatalogRoot() {
    const tree = $("tree");
    tree.innerHTML = "";
    if (!state.selectedId) {
      setMsg("tree-msg", "请选择连接");
      return;
    }
    setMsg("tree-msg", "加载中…");
    try {
      const page = await loadCatalog({ source_id: state.selectedId, limit: 50 });
      if (page.labels) {
        state.labels = {
          namespace: page.labels.namespace_label || state.labels.namespace,
          collection: page.labels.collection_label || state.labels.collection,
          field: page.labels.field_label || state.labels.field,
        };
      }
      const root = document.createElement("div");
      const srcNode = document.createElement("div");
      srcNode.className = "node" + (state.overlayKind === "source" ? " active" : "");
      srcNode.textContent = "数据源";
      if (page.source_patched || page.patched) srcNode.appendChild(patchedBadge(true));
      srcNode.addEventListener("click", async () => {
        state.overlayKind = "source";
        state.overlayNs = null;
        state.overlayColl = null;
        await loadSourceOverlay();
        await loadHistory();
        highlightTree();
      });
      root.appendChild(srcNode);
      await renderLevel(root, page, { source_id: state.selectedId });
      tree.appendChild(root);
      setMsg("tree-msg", "");
    } catch (err) {
      setMsg("tree-msg", err.message, "err");
    }
  }

  async function renderLevel(parent, page, base) {
    const items = page.items || [];
    for (const item of items) {
      if (item.collection) {
        const row = document.createElement("div");
        row.className = "node";
        row.dataset.ns = item.namespace || "";
        row.dataset.coll = item.collection;
        row.textContent = (state.labels.collection || "集合") + " · " + item.collection;
        if (item.patched) row.appendChild(patchedBadge(true));
        row.addEventListener("click", () => openCollection(item.namespace, item.collection));
        parent.appendChild(row);
      } else if (item.namespace) {
        const det = document.createElement("details");
        const sum = document.createElement("summary");
        sum.className = "node";
        sum.dataset.ns = item.namespace;
        sum.textContent = (state.labels.namespace || "命名空间") + " · " + item.namespace;
        det.appendChild(sum);
        det.addEventListener("toggle", async () => {
          if (!det.open || det.dataset.loaded) return;
          det.dataset.loaded = "1";
          try {
            const sub = await loadCatalog({
              source_id: state.selectedId,
              namespace: item.namespace,
              limit: 50,
            });
            await renderLevel(det, sub, { ...base, namespace: item.namespace });
            if (sub.next_cursor) addMore(det, { ...base, namespace: item.namespace }, sub.next_cursor);
          } catch (err) {
            const p = document.createElement("p");
            p.className = "msg err";
            p.textContent = err.message;
            det.appendChild(p);
          }
        });
        parent.appendChild(det);
      }
    }
    if (page.next_cursor) addMore(parent, base, page.next_cursor);
  }

  function addMore(parent, base, cursor) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "outline";
    btn.textContent = "加载更多";
    btn.style.width = "auto";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const page = await loadCatalog({ ...base, cursor, limit: 50 });
        btn.remove();
        await renderLevel(parent, page, base);
      } catch (err) {
        btn.disabled = false;
        setMsg("tree-msg", err.message, "err");
      }
    });
    parent.appendChild(btn);
  }

  function highlightTree() {
    for (const el of $("tree").querySelectorAll(".node")) {
      const isSrc = !el.dataset.ns && !el.dataset.coll;
      const matchColl =
        state.overlayKind === "collection" &&
        el.dataset.ns === (state.overlayNs || "") &&
        el.dataset.coll === state.overlayColl;
      const matchSrc = state.overlayKind === "source" && isSrc && el.textContent.startsWith("数据源");
      el.classList.toggle("active", !!(matchColl || matchSrc));
    }
  }

  async function openCollection(ns, coll) {
    state.overlayKind = "collection";
    state.overlayNs = ns;
    state.overlayColl = coll;
    highlightTree();
    try {
      const page = await loadCatalog({
        source_id: state.selectedId,
        namespace: ns,
        collection: coll,
        limit: 50,
      });
      const item = (page.items && page.items[0]) || {};
      state.columns = page.columns || item.columns || [];
      const fp = item.field_patched || {};
      const host = document.querySelector(
        '#tree .node[data-coll="' + CSS.escape(coll) + '"][data-ns="' + CSS.escape(ns || "") + '"]'
      );
      if (host) {
        let box = host.nextElementSibling;
        if (!box || !box.classList.contains("field-children")) {
          box = document.createElement("div");
          box.className = "field-children";
          host.after(box);
        }
        box.innerHTML = "";
        for (const col of state.columns) {
          const frow = document.createElement("div");
          frow.className = "node field";
          frow.textContent = (state.labels.field || "字段") + " · " + col.name;
          if (fp[col.name]) frow.appendChild(patchedBadge(true));
          box.appendChild(frow);
        }
      }
    } catch {
      state.columns = [];
    }
    await loadCollectionOverlay();
    await loadHistory();
  }

  function showEditor(kind) {
    $("editor-form").classList.remove("hidden");
    $("editor-source").classList.toggle("hidden", kind !== "source");
    $("editor-collection").classList.toggle("hidden", kind !== "collection");
  }

  async function loadSourceOverlay() {
    if (!state.selectedId) return;
    showEditor("source");
    $("editor-hint").textContent = "数据源补丁：库描述 + 查询规则";
    const data = await api("/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay");
    const body = data.body || {};
    $("src-desc").value = body.description || "";
    $("src-rules").value = body.query_rules || "";
    setMsg("editor-msg", data.patched ? "已修" : "");
  }

  function overlayCollectionPath() {
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

  async function loadCollectionOverlay() {
    showEditor("collection");
    $("editor-hint").textContent =
      (state.labels.collection || "集合") + " " + state.overlayNs + "." + state.overlayColl;
    const data = await api(overlayCollectionPath());
    const body = data.body || {};
    $("coll-desc").value = body.description || "";
    const fields = body.fields || {};
    const box = $("field-list");
    box.innerHTML = "";
    const names = new Set([
      ...Object.keys(fields),
      ...state.columns.map((c) => c.name),
    ]);
    if (names.size === 0) {
      const p = document.createElement("p");
      p.className = "msg";
      p.textContent = "暂无字段，可在保存后按名补充";
      box.appendChild(p);
    }
    for (const name of names) {
      const label = document.createElement("label");
      const caption = (state.labels.field || "字段") + " · " + name;
      label.textContent = caption;
      const input = document.createElement("input");
      input.type = "text";
      input.dataset.field = name;
      input.value = fields[name] || "";
      const col = state.columns.find((c) => c.name === name);
      if (col && col.comment) input.placeholder = col.comment;
      label.appendChild(input);
      box.appendChild(label);
    }
    setMsg("editor-msg", data.patched ? "已修" : "");
  }

  function overlayBase() {
    if (state.overlayKind === "collection" && state.overlayNs && state.overlayColl) {
      return overlayCollectionPath();
    }
    return "/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay";
  }

  async function loadHistory() {
    const box = $("hist-list");
    box.innerHTML = "";
    $("hist-diff").textContent = "";
    if (!state.selectedId) {
      setMsg("hist-msg", "请选择连接");
      return;
    }
    try {
      const data = await api(overlayBase() + "/versions");
      const versions = Array.isArray(data) ? data : data.versions || [];
      state.versions = versions;
      state.headMeta = data.head || null;
      if (!versions.length) {
        setMsg("hist-msg", "暂无版本");
        return;
      }
      setMsg("hist-msg", "");
      for (const ver of versions) {
        const card = document.createElement("div");
        card.className = "version";
        if (ver.kind === "named") card.classList.add("named");
        if (ver.current) card.classList.add("current");
        const row = document.createElement("div");
        row.className = "row";
        const left = document.createElement("div");
        const kind = ver.kind === "named" ? "命名" : "自动";
        const label = ver.label ? " · " + ver.label : "";
        const cur = ver.current ? " · 当前" : "";
        left.textContent = kind + label + cur;
        const sub = document.createElement("div");
        sub.className = "meta";
        sub.textContent = (ver.id || "").slice(0, 8) + "  " + (ver.created_at || "");
        left.appendChild(sub);
        const btns = document.createElement("div");
        btns.className = "btns";
        const mk = (text, fn) => {
          const b = document.createElement("button");
          b.type = "button";
          b.textContent = text;
          b.addEventListener("click", fn);
          return b;
        };
        btns.append(
          mk("查看", () => viewVersion(ver)),
          mk("diff", () => diffVersion(ver)),
          mk("恢复", () => restoreVersion(ver))
        );
        if (ver.kind !== "named") {
          btns.append(mk("命名", () => nameVersion(ver)));
        }
        row.append(left, btns);
        card.appendChild(row);
        box.appendChild(card);
      }
    } catch (err) {
      setMsg("hist-msg", err.message, "err");
    }
  }

  async function viewVersion(ver) {
    const data = await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id));
    $("hist-diff").textContent = JSON.stringify(data.body || data, null, 2);
  }

  async function diffVersion(ver) {
    const toId = (state.headMeta && state.headMeta.id) || (state.versions[0] && state.versions[0].id);
    if (!toId) return;
    const data = await api(
      overlayBase() +
        "/diff?from=" +
        encodeURIComponent(ver.id) +
        "&to=" +
        encodeURIComponent(toId)
    );
    $("hist-diff").textContent = data.diff || data || "";
  }

  async function restoreVersion(ver) {
    if (!confirm("恢复到该版本？当前 HEAD 会先快照。")) return;
    await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id) + "/restore", {
      method: "POST",
    });
    if (state.overlayKind === "collection") await loadCollectionOverlay();
    else await loadSourceOverlay();
    await loadHistory();
    await loadCatalogRoot();
    setMsg("hist-msg", "已恢复", "ok");
  }

  async function nameVersion(ver) {
    const label = prompt("给自动版命名", ver.label || "");
    if (!label) return;
    await api(overlayBase() + "/versions/" + encodeURIComponent(ver.id) + "/name", {
      method: "POST",
      body: { label },
    });
    await loadHistory();
  }

  function bindTabs() {
    for (const btn of document.querySelectorAll(".tabs [data-tab]")) {
      btn.addEventListener("click", () => {
        for (const b of document.querySelectorAll(".tabs [data-tab]")) {
          b.setAttribute("aria-current", b === btn ? "true" : "false");
        }
        $("tab-catalog").classList.toggle("hidden", btn.dataset.tab !== "catalog");
        $("tab-history").classList.toggle("hidden", btn.dataset.tab !== "history");
        $("tab-bundle").classList.toggle("hidden", btn.dataset.tab !== "bundle");
        if (btn.dataset.tab === "history") loadHistory();
      });
    }
  }

  async function init() {
    bindTabs();
    $("engine-select").addEventListener("change", () => renderEngineFields());
    $("btn-new").addEventListener("click", () => {
      state.selectedId = null;
      fillConnectionForm(null);
      renderConnections();
      $("tree").innerHTML = "";
      $("editor-form").classList.add("hidden");
    });
    $("conn-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        const payload = {
          name: $("conn-name").value.trim(),
          engine: $("engine-select").value,
          config: readEngineConfig(),
        };
        const id = $("conn-id").value;
        let saved;
        if (id) {
          saved = await api("/api/connections/" + encodeURIComponent(id), {
            method: "PUT",
            body: payload,
          });
        } else {
          saved = await api("/api/connections", { method: "POST", body: payload });
        }
        setMsg("conn-msg", "已保存", "ok");
        await refreshConnections();
        await selectConnection(saved.id);
      } catch (err) {
        setMsg("conn-msg", err.message, "err");
      }
    });
    $("btn-ping").addEventListener("click", async () => {
      const id = $("conn-id").value || state.selectedId;
      if (!id) {
        setMsg("conn-msg", "请先保存连接", "err");
        return;
      }
      try {
        await api("/api/connections/" + encodeURIComponent(id) + "/ping", { method: "POST" });
        setMsg("conn-msg", "连通正常", "ok");
      } catch (err) {
        setMsg("conn-msg", err.message, "err");
      }
    });
    $("btn-del").addEventListener("click", async () => {
      const id = $("conn-id").value || state.selectedId;
      if (!id) return;
      if (!confirm("删除该连接？")) return;
      try {
        await api("/api/connections/" + encodeURIComponent(id), { method: "DELETE" });
        state.selectedId = null;
        await refreshConnections();
        fillConnectionForm(null);
        $("tree").innerHTML = "";
        setMsg("conn-msg", "已删除", "ok");
      } catch (err) {
        setMsg("conn-msg", err.message, "err");
      }
    });
    $("editor-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (!state.selectedId) return;
      try {
        if (state.overlayKind === "collection") {
          const fields = {};
          for (const input of $("field-list").querySelectorAll("[data-field]")) {
            if (input.value.trim()) fields[input.dataset.field] = input.value.trim();
          }
          await api(overlayCollectionPath(), {
            method: "PUT",
            body: { description: $("coll-desc").value, fields },
          });
        } else {
          await api("/api/sources/" + encodeURIComponent(state.selectedId) + "/overlay", {
            method: "PUT",
            body: {
              description: $("src-desc").value,
              query_rules: $("src-rules").value,
            },
          });
        }
        setMsg("editor-msg", "已保存", "ok");
        await loadCatalogRoot();
        await loadHistory();
      } catch (err) {
        setMsg("editor-msg", err.message, "err");
      }
    });
    $("btn-export").addEventListener("click", async () => {
      try {
        const data = await api("/api/export", {
          method: "POST",
          body: { include_history: $("include-history").checked },
        });
        $("bundle-box").value = JSON.stringify(data, null, 2);
        setMsg("bundle-msg", "已导出", "ok");
      } catch (err) {
        setMsg("bundle-msg", err.message, "err");
      }
    });
    $("btn-import").addEventListener("click", async () => {
      try {
        let raw = "";
        const fileEl = $("import-file");
        if (fileEl && fileEl.files && fileEl.files[0]) {
          raw = await fileEl.files[0].text();
        } else {
          raw = $("bundle-box").value.trim();
        }
        if (!raw) throw new Error("请选择文件或粘贴导出 JSON");
        await api("/api/import", { method: "POST", body: JSON.parse(raw) });
        await refreshConnections();
        setMsg("bundle-msg", "已导入", "ok");
      } catch (err) {
        setMsg("bundle-msg", err.message, "err");
      }
    });

    const enginesResp = await api("/api/engines");
    state.engines = Array.isArray(enginesResp) ? enginesResp : enginesResp.engines || [];
    renderEngineSelect();
    await refreshConnections();
  }

  init().catch((err) => setMsg("conn-msg", err.message, "err"));
})();
