import { api } from "../api.js";

export function renderPendingOrRejected(user) {
  const isRejected = user.status === "rejected";
  return `
    <div class="empty-state">
      <div class="icon">${isRejected ? "❌" : "⏳"}</div>
      <h2>${isRejected ? "Registration not approved" : "Approval pending"}</h2>
      <p>${
        isRejected
          ? "Your registration was not approved. Contact the Social Director if you think this is a mistake."
          : "Your registration is waiting on the Social Director. You'll get a Telegram message once you're approved."
      }</p>
    </div>
  `;
}

export function renderRegister(root, onRegistered) {
  root.innerHTML = `
    <h1>Welcome to Social Port Hub</h1>
    <p>Enter your email to request access. The Social Director will approve you and assign your committee.</p>
    <form id="register-form">
      <div class="field">
        <label for="email">NUS Email</label>
        <input type="email" id="email" name="email" required placeholder="you@example.com" />
      </div>
      <div class="field">
        <label for="telegram_username">Telegram handle</label>
        <input type="text" id="telegram_username" name="telegram_username" required placeholder="@yourusername" pattern="@?[A-Za-z0-9_]{5,32}" />
        <div class="field-hint">Include the @ if possible.</div>
      </div>
      <div class="field">
        <label for="display_name">Display name</label>
        <input type="text" id="display_name" name="display_name" placeholder="How committee members will see you" />
      </div>
      <div id="register-error"></div>
      <button type="submit" class="btn">Request Access</button>
    </form>
  `;

  root.querySelector("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = root.querySelector("#register-error");
    errorEl.innerHTML = "";
    const submitBtn = e.target.querySelector("button");
    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting…";

    try {
      const user = await api.post("/api/auth/register", {
        email: e.target.email.value.trim(),
        telegram_username: e.target.telegram_username.value.trim(),
        display_name: e.target.display_name.value.trim() || null,
      });
      onRegistered(user);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = "Request Access";
    }
  });
}
