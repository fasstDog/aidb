/** 配置台 API。引擎列表必须 GET /api/engines，表单吃 form_schema。 */
export async function api(path, opts = {}) {
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

export function engineRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.engines)) return payload.engines;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

export function schemaFields(engine) {
  if (!engine) return [];
  const schema = engine.form_schema || {};
  return Array.isArray(schema.fields) ? schema.fields : [];
}

export function isSecretField(field) {
  return !!field && (field.type === "password" || field.secret);
}
