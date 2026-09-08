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
  const draftKey = "social-port-hub-proposal-draft";
  const saved = JSON.parse(localStorage.getItem(draftKey) || "null") || {};
  root.innerHTML = `
    <div class="page-header">
      <span class="back" data-nav="home">&larr; Back</span>
    </div>
    <h1>New Proposal</h1>
    <form id="proposal-form">
      <div class="field">
        <label for="title">Title</label>
        <input type="text" id="title" name="title" required value="${escapeHtml(saved.title)}" />
      </div>
      <div class="field">
        <label for="category">Category</label>
        <select id="category" name="category" required>
          <option value="event" ${saved.category === "event" ? "selected" : ""}>Event</option>
          <option value="initiative" ${saved.category === "initiative" ? "selected" : ""}>Initiative</option>
          <option value="decor" ${saved.category === "decor" ? "selected" : ""}>Decor</option>
          <option value="pantry_cleaning" ${!saved.category || saved.category === "pantry_cleaning" ? "selected" : ""}>Pantry Cleaning</option>
        </select>
      </div>
      <div class="field">
        <label for="description">Description</label>
        <textarea id="description" name="description">${escapeHtml(saved.description)}</textarea>
      </div>
      <div class="field">
        <label for="event_date">Event date</label>
        <input type="date" id="event_date" name="event_date" value="${escapeHtml(saved.event_date)}" />
      </div>
      <div class="field">
        <label for="doc_link">Link / PDF URL <span id="doc-required-hint"></span></label>
        <input type="url" id="doc_link" name="doc_link" placeholder="https://" value="${escapeHtml(saved.doc_link)}" />
      </div>
      <div class="field" id="poster-field">
        <label for="poster">Poster <span class="field-hint">Required for Event and Initiative</span></label>
        <input type="file" id="poster" name="poster" accept="image/jpeg,image/png,image/webp,application/pdf" />
      </div>
      <div class="field">
        <label for="blast_message">Blast message (optional)</label>
        <textarea id="blast_message" name="blast_message" placeholder="Message to accompany the event announcement">${escapeHtml(saved.blast_message)}</textarea>
      </div>
      <div id="form-error"></div>
      <div class="btn-row"><button type="button" class="btn btn-secondary" id="save-draft">Save Draft</button><button type="submit" class="btn">Submit for Review</button></div>
    </form>
  `;

  const form = root.querySelector("#proposal-form");
  const category = root.querySelector("#category");
  const posterField = root.querySelector("#poster-field");
  const docLink = root.querySelector("#doc_link");
  const updateRequirements = () => {
    const needsPoster = ["event", "initiative"].includes(category.value);
    const needsDoc = category.value === "decor";
    posterField.style.display = needsPoster ? "block" : "none";
    root.querySelector("#poster").required = false; // upload happens after proposal creation
    docLink.required = needsDoc;
    root.querySelector("#doc-required-hint").textContent = needsDoc ? "(required for Decor)" : "(optional)";
  };
  category.addEventListener("change", updateRequirements);
  updateRequirements();

  root.querySelector("#save-draft").addEventListener("click", () => {
    localStorage.setItem(draftKey, JSON.stringify(Object.fromEntries(new FormData(form).entries())));
    root.querySelector("#form-error").innerHTML = `<p>Draft saved on this device.</p>`;
  });

  root.querySelector("#proposal-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = root.querySelector("#form-error");
    errorEl.innerHTML = "";
    const btn = e.target.querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "Submitting…";

    try {
      const categoryValue = e.target.category.value;
      const poster = e.target.poster.files[0];
      if (["event", "initiative"].includes(categoryValue) && !poster) {
        throw new Error("Please select a poster for this category.");
      }
      if (categoryValue === "decor" && !e.target.doc_link.value.trim()) {
        throw new Error("Please provide a link or PDF URL for Decor.");
      }
      const proposal = await api.post("/api/proposals", {
        title: e.target.title.value.trim(),
        category: categoryValue,
        description: e.target.description.value.trim() || null,
        event_date: e.target.event_date.value || null,
        doc_link: e.target.doc_link.value.trim() || null,
        blast_message: e.target.blast_message.value.trim() || null,
      });
      if (poster) {
        const formData = new FormData();
        formData.append("poster", poster);
        await api.upload(`/api/proposals/${proposal.id}/poster`, formData);
      } else if (["event", "initiative"].includes(e.target.category.value)) {
        throw new Error("Please select a poster for this category.");
      }
      localStorage.removeItem(draftKey);
      navigate(`proposal/${proposal.id}`);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
      btn.disabled = false;
      btn.textContent = "Submit for Review";
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

    <div class="card"><h3>Category</h3><p style="color:var(--text)">${escapeHtml(proposal.category.replaceAll("_", " "))}</p>
      ${proposal.blast_message ? `<h3>Blast message</h3><p style="color:var(--text); white-space:pre-wrap;">${escapeHtml(proposal.blast_message)}</p>` : ""}
      ${proposal.poster_filename ? `<p><a href="/api/proposals/${proposal.id}/poster" target="_blank" rel="noopener">View poster</a></p>` : ""}
    </div>

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
        <label for="e-category">Category</label>
        <select id="e-category">
          <option value="event" ${proposal.category === "event" ? "selected" : ""}>Event</option>
          <option value="initiative" ${proposal.category === "initiative" ? "selected" : ""}>Initiative</option>
          <option value="decor" ${proposal.category === "decor" ? "selected" : ""}>Decor</option>
          <option value="pantry_cleaning" ${proposal.category === "pantry_cleaning" ? "selected" : ""}>Pantry Cleaning</option>
        </select>
      </div>
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
      <div class="field">
        <label for="e-blast_message">Blast message</label>
        <textarea id="e-blast_message">${escapeHtml(proposal.blast_message)}</textarea>
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
        category: slot.querySelector("#e-category").value,
        title: slot.querySelector("#e-title").value.trim(),
        description: slot.querySelector("#e-description").value.trim() || null,
        event_date: slot.querySelector("#e-event_date").value || null,
        doc_link: slot.querySelector("#e-doc_link").value.trim() || null,
        blast_message: slot.querySelector("#e-blast_message").value.trim() || null,
      });
      navigate(`proposal/${proposal.id}`);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
