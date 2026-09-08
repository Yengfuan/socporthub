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

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
  upload: (path, body) => request("POST", path, body),
  delete: (path) => request("DELETE", path),
  ApiError,
  getInitData,
};
