const tg = window.Telegram?.WebApp;

// Outside Telegram (plain browser, local dev) there's no real initData. The backend
// only accepts the `dev_telegram_id` shortcut when ENVIRONMENT=development and no
// TELEGRAM_BOT_TOKEN is set — see api/auth.py:verify_init_data.
function getInitData() {
  if (tg?.initData) return tg.initData;
  const stored = localStorage.getItem("dev_telegram_id") || "1000001";
  return `dev_telegram_id=${stored}`;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  const isForm = body instanceof FormData;
  const res = await fetch(path, {
    method,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      "X-Telegram-Init-Data": getInitData(),
    },
    body: body !== undefined ? (isForm ? body : JSON.stringify(body)) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

async function requestBlob(path) {
  const res = await fetch(path, {
    method: "GET",
    headers: { "X-Telegram-Init-Data": getInitData() },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, detail);
  }

  // Files kept in object storage come back as a short-lived signed link instead of
  // bytes (serverless responses are size-capped). The link needs no auth header.
  if (res.headers.get("Content-Type")?.includes("application/json")) {
    const { signed_url: signedUrl, filename } = await res.json();
    const file = await fetch(signedUrl);
    if (!file.ok) throw new ApiError(file.status, "Could not download the file");
    return { blob: await file.blob(), filename: filename || "poster" };
  }

  return {
    blob: await res.blob(),
    filename: getFilename(res.headers.get("Content-Disposition")),
  };
}

// Upload a proposal poster. With object storage enabled the file goes straight from the
// browser to storage through a one-time URL (no 4.5 MB serverless body limit); otherwise
// it is posted to the API as before.
async function uploadPoster(proposalId, file) {
  const base = `/api/proposals/${proposalId}/poster`;
  const ticket = await request("POST", `${base}/upload-url`, {
    filename: file.name || "poster",
    content_type: file.type,
    size: file.size,
  });
  if (!ticket.upload_url) {
    const formData = new FormData();
    formData.append("poster", file);
    return request("POST", base, formData);
  }
  const put = await fetch(ticket.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type, "x-upsert": "true" },
    body: file,
  });
  if (!put.ok) throw new ApiError(put.status, "Poster upload failed, please try again");
  return request("POST", `${base}/confirm`, { path: ticket.path, filename: file.name || "poster" });
}

function getFilename(contentDisposition) {
  const match = contentDisposition?.match(/filename="([^"]+)"/i);
  return match?.[1] || "poster";
}

export const api = {
  get: (path) => request("GET", path),
  getBlob: requestBlob,
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
  put: (path, body) => request("PUT", path, body),
  upload: (path, body) => request("POST", path, body),
  uploadPoster,
  delete: (path) => request("DELETE", path),
  ApiError,
  getInitData,
};
