import { api } from "../api.js";
import { statusBadge } from "../components/status-badge.js";

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
  const proposal = await api.get(`/api/proposals/${proposalId}`);

  const isAdmin = user.role === "admin";
  const isOwner = proposal.submitted_by === user.id;
  const canEdit = isOwner && proposal.status === "needs_action";
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

    ${canEdit ? `<button class="btn btn-secondary" id="edit-btn">Edit Proposal</button>` : ""}

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
  `;

  root.querySelector("#advance-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, nextStatus);
  });
  root.querySelector("#revert-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, "needs_action");
  });
  root.querySelector("#edit-btn")?.addEventListener("click", () => {
    renderEditForm(root.querySelector("#edit-form-slot"), proposal, navigate);
  });

  async function changeStatus(btn, status) {
    btn.disabled = true;
    const errorEl = root.querySelector("#detail-error");
    try {
      await api.patch(`/api/proposals/${proposal.id}`, { status });
      renderProposalDetail(root, user, proposalId, navigate);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
      btn.disabled = false;
    }
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
