export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data || {};
  }
}

async function parse(res) {
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) {
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error) {
      throw new ApiError(data.error || `请求失败（${res.status}）`, res.status, data);
    }
    return data;
  }
  if (!res.ok) throw new ApiError(`请求失败（${res.status}）`, res.status);
  return { ok: true };
}

export const getJSON = (url) =>
  fetch(url, { headers: { Accept: "application/json" } }).then(parse);

function toForm(fields) {
  const fd = new FormData();
  for (const [key, value] of Object.entries(fields || {})) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) value.forEach((item) => fd.append(key, item));
    else fd.append(key, value instanceof File ? value : String(value));
  }
  return fd;
}

export const postForm = (url, fields) =>
  fetch(url, { method: "POST", body: toForm(fields) }).then(parse);

export const postFormJSON = (url, fields) =>
  fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: toForm(fields),
  }).then(parse);

export const postJSON = (url, body) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then(parse);

export const postEmpty = (url) => fetch(url, { method: "POST" }).then(parse);

export const errorText = (err) => (err instanceof Error ? err.message : String(err));
