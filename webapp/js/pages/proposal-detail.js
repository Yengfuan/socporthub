import { api } from "../api.js";
import { statusBadge } from "../components/status-badge.js";
import { renderDisposableSection } from "../components/disposable-form.js";

const NEXT_STATUS = {
  needs_action: "in_review",
  in_review: "submitted",
  submitted: "finished",
};

const NEXT_STATUS_LABEL = {
  needs_action: "Move to In Review",
  in_review: "Mark Submitted",
  submitted: "Mark Finished",
};

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function formatTimestamp(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function renderNewProposal(root, navigate) {
  root.innerHTML = `
    <div class="page-header">
      <span class="back" data-nav="home">&larr; Back</span>
    </div>
    <h1>New Proposal</h1>
    <form id="proposal-form">
      <div class="field">
        <label for="title">Title</label>
        <input type="text" id="title" name="title" required />
      </div>
      <div class="field">
        <label for="description">Description</label>
        <textarea id="description" name="description"></textarea>
      </div>
      <div class="field">
        <label for="event_date">Event date</label>
        <input type="date" id="event_date" name="event_date" />
      </div>
      <div class="field">
        <label for="doc_link">Google Doc / link (optional)</label>
        <input type="url" id="doc_link" name="doc_link" placeholder="https://" />
      </div>
      <div id="form-error"></div>
      <button type="submit" class="btn">Submit Proposal</button>
    </form>
  `;

  root.querySelector("#proposal-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = root.querySelector("#form-error");
    errorEl.innerHTML = "";
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    btn.textContent = "Submitting…";

    try {
      const proposal = await api.post("/api/proposals", {
        title: e.target.title.value.trim(),
        description: e.target.description.value.trim() || null,
        event_date: e.target.event_date.value || null,
        doc_link: e.target.doc_link.value.trim() || null,
      });
      navigate(`proposal/${proposal.id}`);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
      btn.disabled = false;
      btn.textContent = "Submit Proposal";
    }
  });
}

export async function renderProposalDetail(root, user, proposalId, navigate) {
  root.innerHTML = `<div class="loading">Loading…</div>`;
  const [proposal, comments] = await Promise.all([
    api.get(`/api/proposals/${proposalId}`),
    api.get(`/api/proposals/${proposalId}/comments`),
  ]);

  const isAdmin = user.role === "admin";
  const isOwner = proposal.submitted_by === user.id;
  // Admins can edit a proposal's fields (including clearing a stray event_date) at any
  // status; a regular owner can only edit their own while it's still needs_action.
  const canEdit = isAdmin || (isOwner && proposal.status === "needs_action");
  const nextStatus = NEXT_STATUS[proposal.status];

  root.innerHTML = `
    <div class="page-header">
      <span class="back" data-nav="${isAdmin ? "admin" : "home"}">&larr; Back</span>
      ${statusBadge(proposal.status)}
    </div>

    <h1>${escapeHtml(proposal.title)}</h1>
    <p>${escapeHtml(proposal.committee_name)} · Submitted by ${escapeHtml(proposal.submitter_name || "")}</p>

    <div class="card">
      <h3>Description</h3>
      <p style="color: var(--text); white-space: pre-wrap;">${
        escapeHtml(proposal.description) || "<span style=\"color:var(--text-muted)\">No description</span>"
      }</p>

      <h3>Event date</h3>
      <p style="color: var(--text)">${proposal.event_date || "Not set"}</p>

      <h3>Supporting document</h3>
      <p>${
        proposal.doc_link
          ? `<a href="${escapeHtml(proposal.doc_link)}" target="_blank" rel="noopener">${escapeHtml(
              proposal.doc_link
            )}</a>`
          : "None linked"
      }</p>
    </div>

    <div id="disposable-slot"></div>

    ${canEdit ? `<button class="btn btn-secondary" id="edit-btn">Edit Proposal</button>` : ""}

    ${
      isAdmin && (nextStatus || proposal.status === "in_review")
        ? `<div class="field" style="margin-top:16px">
             <label for="status-comment">Note to submitter (optional)</label>
             <textarea id="status-comment" placeholder="Explain what needs to change, or add context…"></textarea>
           </div>`
        : ""
    }
    ${
      isAdmin && nextStatus
        ? `<button class="btn" id="advance-btn">${NEXT_STATUS_LABEL[proposal.status]}</button>`
        : ""
    }
    ${
      isAdmin && proposal.status === "in_review"
        ? `<button class="btn btn-secondary" id="revert-btn" style="margin-top:8px">Send back to Needs Action</button>`
        : ""
    }

    <div id="detail-error"></div>
    <div id="edit-form-slot"></div>

    ${!isAdmin ? `<button class="btn btn-secondary" id="remind-btn" style="margin-top:12px">Remind Admin</button>` : ""}

    <h2 style="margin-top:24px">Comments</h2>
    <div id="comments-list">
      ${
        comments.length
          ? comments
              .map(
                (c) => `
        <div class="card">
          <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-muted); margin-bottom:4px;">
            <span>${escapeHtml(c.author_name || "")}</span>
            <span>${formatTimestamp(c.created_at)}</span>
          </div>
          <div style="white-space:pre-wrap;">${escapeHtml(c.body)}</div>
        </div>`
              )
              .join("")
          : `<p>No comments yet.</p>`
      }
    </div>
    <form id="comment-form">
      <div class="field">
        <textarea id="comment-body" placeholder="Add a comment…" required></textarea>
      </div>
      <button type="submit" class="btn btn-secondary">Post Comment</button>
    </form>
  `;

  renderDisposableSection(root.querySelector("#disposable-slot"), user, proposal);
  if (proposal.status === "in_review") renderEmailSection(root, user, proposal, navigate);

  root.querySelector("#advance-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, nextStatus);
  });
  root.querySelector("#revert-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, "needs_action");
  });
  root.querySelector("#edit-btn")?.addEventListener("click", () => {
    renderEditForm(root.querySelector("#edit-form-slot"), proposal, navigate);
  });
  root.querySelector("#comment-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = root.querySelector("#comment-body").value.trim();
    if (!body) return;
    await api.post(`/api/proposals/${proposal.id}/comments`, { body });
    renderProposalDetail(root, user, proposalId, navigate);
  });
  root.querySelector("#remind-btn")?.addEventListener("click", async (e) => {
    const message = window.prompt("What should the admin review?");
    if (!message?.trim()) return;
    e.target.disabled = true;
    try {
      await api.post("/api/reminders", { message: message.trim(), target_type: "proposal", target_id: proposal.id });
      e.target.textContent = "Reminder sent";
    } catch (err) {
      root.querySelector("#detail-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
      e.target.disabled = false;
    }
  });

  async function changeStatus(btn, newStatus) {
    btn.disabled = true;
    const errorEl = root.querySelector("#detail-error");
    const comment = root.querySelector("#status-comment")?.value.trim() || null;
    try {
      await api.patch(`/api/proposals/${proposal.id}`, { status: newStatus, comment });
      renderProposalDetail(root, user, proposalId, navigate);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
      btn.disabled = false;
    }
  }
}

async function renderEmailSection(root, user, proposal, navigate) {
  const slot = document.createElement("div");
  slot.id = "email-slot";
  const disposableSlot = root.querySelector("#disposable-slot");
  disposableSlot.after(slot);
  if (proposal.status !== "in_review") return;
  try {
    const draft = await api.get(`/api/email/preview/${proposal.id}`);
    slot.innerHTML = `<div class="card"><h3>Confirmation Email</h3>
      <div class="field"><label for="email-recipient">To</label><input id="email-recipient" value="${escapeHtml(draft.recipient)}" disabled /></div>
      <div class="field"><label for="email-subject">Subject</label><input id="email-subject" value="${escapeHtml(draft.subject)}" ${user.role === "admin" ? "" : "disabled"} /></div>
      <div class="field"><label for="email-body">Message</label><textarea id="email-body" ${user.role === "admin" ? "" : "disabled"}>${escapeHtml(draft.body)}</textarea></div>
      <div id="email-error"></div>${user.role === "admin" ? `<div class="btn-row"><button class="btn btn-secondary" id="save-email">Save Draft</button><button class="btn" id="send-email">Send & Submit</button></div>` : `<p>Email preview only.</p>`}
    </div>`;
    if (user.role !== "admin") return;
    const save = async () => api.patch(`/api/email/preview/${proposal.id}`, { subject: slot.querySelector("#email-subject").value, body: slot.querySelector("#email-body").value });
    slot.querySelector("#save-email").addEventListener("click", async () => {
      try { await save(); slot.querySelector("#email-error").innerHTML = `<p>Draft saved.</p>`; } catch (err) { slot.querySelector("#email-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`; }
    });
    slot.querySelector("#send-email").addEventListener("click", async (e) => {
      e.target.disabled = true;
      try { await save(); await api.post(`/api/email/send/${proposal.id}`); await renderProposalDetail(root, user, proposal.id, navigate); }
      catch (err) { slot.querySelector("#email-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`; e.target.disabled = false; }
    });
  } catch (err) {
    slot.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
  }
}

function renderEditForm(slot, proposal, navigate) {
  slot.innerHTML = `
    <form id="edit-form" style="margin-top:16px">
      <div class="field">
        <label for="e-title">Title</label>
        <input type="text" id="e-title" value="${escapeHtml(proposal.title)}" required />
      </div>
      <div class="field">
        <label for="e-description">Description</label>
        <textarea id="e-description">${escapeHtml(proposal.description)}</textarea>
      </div>
      <div class="field">
        <label for="e-event_date">Event date</label>
        <input type="date" id="e-event_date" value="${proposal.event_date || ""}" />
      </div>
      <div class="field">
        <label for="e-doc_link">Google Doc / link</label>
        <input type="url" id="e-doc_link" value="${escapeHtml(proposal.doc_link)}" />
      </div>
      <div id="edit-error"></div>
      <button type="submit" class="btn">Save Changes</button>
    </form>
  `;

  slot.querySelector("#edit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = slot.querySelector("#edit-error");
    try {
      await api.patch(`/api/proposals/${proposal.id}`, {
        title: slot.querySelector("#e-title").value.trim(),
        description: slot.querySelector("#e-description").value.trim() || null,
        event_date: slot.querySelector("#e-event_date").value || null,
        doc_link: slot.querySelector("#e-doc_link").value.trim() || null,
      });
      navigate(`proposal/${proposal.id}`);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
