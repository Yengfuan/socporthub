import { api } from "../api.js";

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

export async function renderReminders(root, user) {
  const reminders = await api.get("/api/reminders");
  const isAdmin = user.role === "admin";
  root.innerHTML = `
    <h1>Reminders</h1>
    ${!isAdmin ? `<form id="reminder-form" class="card">
      <h3>Nudge the admin</h3>
      <div class="field"><label for="reminder-message">Message</label><textarea id="reminder-message" required placeholder="What needs attention?"></textarea></div>
      <div id="reminder-error"></div>
      <button class="btn" type="submit">Send Reminder</button>
    </form>` : ""}
    <h2>${isAdmin ? "Inbox" : "Sent reminders"}</h2>
    <div id="reminder-list">${reminders.length ? reminders.map((r) => reminderCard(r, isAdmin)).join("") : `<div class="empty-state"><p>No reminders yet.</p></div>`}</div>
  `;

  root.querySelector("#reminder-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const error = root.querySelector("#reminder-error");
    try {
      await api.post("/api/reminders", { message: root.querySelector("#reminder-message").value.trim() });
      await renderReminders(root, user);
    } catch (err) {
      error.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    }
  });
  root.querySelectorAll("[data-mark-read]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api.patch(`/api/reminders/${button.dataset.markRead}/read`, {});
      await renderReminders(root, user);
    });
  });
}

function reminderCard(reminder, isAdmin) {
  return `<div class="card ${reminder.is_read ? "reminder-read" : "reminder-unread"}">
    <div class="meta"><span>${escapeHtml(reminder.sender_name || "")}</span><span>${new Date(reminder.created_at).toLocaleString()}</span></div>
    <p style="color:var(--text); white-space:pre-wrap;">${escapeHtml(reminder.message)}</p>
    ${isAdmin && !reminder.is_read ? `<button class="btn btn-secondary" data-mark-read="${reminder.id}">Mark as read</button>` : ""}
  </div>`;
}
