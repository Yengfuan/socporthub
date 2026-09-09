import { api } from "../api.js";

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

export function renderBugReport(root) {
  root.innerHTML = `
    <div class="page-header">
      <span class="back" data-nav="home">&larr; Back</span>
    </div>
    <h1>Report a Bug</h1>
    <p>Tell us what went wrong, what you expected to happen, and any steps that help reproduce it.</p>
    <form id="bug-report-form" class="card">
      <div class="field">
        <label for="bug-message">What happened?</label>
        <textarea id="bug-message" rows="8" required maxlength="5000" placeholder="Describe the problem…"></textarea>
      </div>
      <div id="bug-report-feedback"></div>
      <button class="btn" type="submit" id="bug-report-submit">Send Bug Report</button>
    </form>
    <div class="card">
      <h3>Need a direct response?</h3>
      <p>You can also contact Fengyuan directly on Telegram.</p>
      <a class="btn btn-secondary" href="https://t.me/gnefnuay" target="_blank" rel="noopener">Message @gnefnuay</a>
    </div>
  `;

  root.querySelector("#bug-report-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = root.querySelector("#bug-report-submit");
    const feedback = root.querySelector("#bug-report-feedback");
    button.disabled = true;
    button.textContent = "Sending…";
    feedback.innerHTML = "";
    try {
      await api.post("/api/bug-reports", { message: root.querySelector("#bug-message").value });
      feedback.innerHTML = `<div class="success-banner" role="status">Bug report sent. Thank you!</div>`;
      root.querySelector("#bug-message").value = "";
      button.textContent = "Sent";
    } catch (error) {
      feedback.innerHTML = `<div class="error-banner">${escapeHtml(error.message)}</div>`;
      button.disabled = false;
      button.textContent = "Send Bug Report";
    }
  });
}
