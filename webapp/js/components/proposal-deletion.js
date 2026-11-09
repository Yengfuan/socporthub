import { api } from "../api.js";

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

const DOC_NOTE = "The linked Google Doc and any Drive folder are not deleted.";

// Delete controls on a proposal's page. Admins delete directly (after a confirm);
// the submitter asks, with a reason, and an admin decides.
export async function renderDeletionSection(slot, user, proposal, navigate) {
  if (user.role === "admin") {
    slot.innerHTML = `<button class="btn btn-secondary" id="delete-proposal-btn" style="margin-top:8px">Delete proposal</button>`;
    slot.querySelector("#delete-proposal-btn").addEventListener("click", async (e) => {
      const ok = confirm(
        `Permanently delete "${proposal.title}"?\n\nThis removes its comments, history, disposable request, grading and calendar entry. This can't be undone. ${DOC_NOTE}`
      );
      if (!ok) return;
      e.target.disabled = true;
      try {
        await api.delete(`/api/proposals/${proposal.id}`);
        navigate("admin");
      } catch (err) {
        e.target.disabled = false;
        slot.insertAdjacentHTML("beforeend", `<div class="error-banner">${escapeHtml(err.message)}</div>`);
      }
    });
    return;
  }

  if (!(user.committees || []).some((c) => c.id === proposal.committee_id)) return;

  const requests = await api.get(`/api/proposal-deletions?proposal_id=${proposal.id}`).catch(() => []);
  const pending = requests.find((r) => r.status === "pending");
  const lastRejected = requests.find((r) => r.status === "rejected");

  if (pending) {
    slot.innerHTML = `<div class="card"><h3>Deletion requested</h3>
      <p>Waiting for an admin to approve. Your reason: ${escapeHtml(pending.reason)}</p></div>`;
    return;
  }

  slot.innerHTML = `
    ${lastRejected ? `<div class="card"><h3>Deletion request rejected</h3><p>${escapeHtml(lastRejected.decision_note || "No note given.")}</p></div>` : ""}
    <button class="btn btn-secondary" id="request-delete-btn" style="margin-top:8px">Request deletion</button>
    <form id="delete-request-form" class="card" style="display:none; margin-top:8px">
      <h3>Why should this proposal be deleted?</h3>
      <div class="field"><textarea name="reason" maxlength="1000" required></textarea></div>
      <div id="delete-request-error"></div>
      <button type="submit" class="btn">Send request to admin</button>
    </form>`;
  const form = slot.querySelector("#delete-request-form");
  slot.querySelector("#request-delete-btn").addEventListener("click", () => {
    form.style.display = form.style.display === "none" ? "block" : "none";
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api.post("/api/proposal-deletions", { proposal_id: proposal.id, reason: form.reason.value.trim() });
      renderDeletionSection(slot, user, proposal, navigate);
    } catch (err) {
      slot.querySelector("#delete-request-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    }
  });
}

// Admin dashboard notice: pending deletion requests with Approve / Reject.
export async function renderDeletionRequests(container, onChange) {
  const requests = await api.get("/api/proposal-deletions").catch(() => []);
  if (!requests.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <div class="card" style="border:2px solid var(--accent)">
      <h3>Deletion requests (${requests.length})</h3>
      ${requests
        .map(
          (r) => `
        <div style="padding:8px 0; border-top:1px solid var(--border)">
          <div class="title">${escapeHtml(r.proposal_title)}</div>
          <div class="meta">${escapeHtml(r.committee_name)} · ${escapeHtml(r.requester_name || "")}</div>
          <p style="color:var(--text)">${escapeHtml(r.reason)}</p>
          <div class="btn-row">
            <button class="btn" style="width:auto; padding:6px 14px;" data-approve-deletion="${r.id}">Approve &amp; delete</button>
            <button class="btn btn-secondary" style="width:auto; padding:6px 14px;" data-reject-deletion="${r.id}">Reject</button>
          </div>
        </div>`
        )
        .join("")}
    </div>`;
  container.querySelectorAll("[data-approve-deletion]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const r = requests.find((x) => x.id === Number(btn.dataset.approveDeletion));
      if (!confirm(`Permanently delete "${r.proposal_title}" and all its data? This can't be undone. ${DOC_NOTE}`)) return;
      btn.disabled = true;
      await api.post(`/api/proposal-deletions/${r.id}/approve`, {});
      onChange();
    });
  });
  container.querySelectorAll("[data-reject-deletion]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const note = window.prompt("Optional note for the requester:", "");
      if (note === null) return;
      btn.disabled = true;
      await api.post(`/api/proposal-deletions/${btn.dataset.rejectDeletion}/reject`, { note: note.trim() || null });
      onChange();
    });
  });
}

// Home page: the user's own requests, so an approved (now gone) proposal isn't a mystery.
export async function renderMyDeletionRequests(container) {
  const requests = await api.get("/api/proposal-deletions").catch(() => []);
  if (!requests.length) return;
  container.innerHTML = `
    <div class="card"><h3>Deletion requests</h3>
      ${requests
        .slice(0, 5)
        .map(
          (r) => `<p style="color:var(--text)"><strong>${escapeHtml(r.proposal_title)}</strong> — ${escapeHtml(r.status)}${
            r.decision_note ? ` (${escapeHtml(r.decision_note)})` : ""
          }</p>`
        )
        .join("")}
    </div>`;
}
