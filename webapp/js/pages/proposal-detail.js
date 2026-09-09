import { api } from "../api.js";
import { statusBadge } from "../components/status-badge.js";
import { renderDisposableSection } from "../components/disposable-form.js";

const NEXT_STATUS = {
  draft: "in_review",
  needs_action: "in_review",
  in_review: "submitted",
  submitted: "finished",
};

const NEXT_STATUS_LABEL = {
  draft: "Submit for Review",
  needs_action: "Resubmit for Review",
  in_review: "Mark Submitted",
  submitted: "Mark Finished",
};

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

const CATEGORY_LABELS = {
  event: "Event",
  initiative: "Initiative",
  decor: "Decor",
  pantry_cleaning: "Pantry Cleaning",
  merch: "Merch",
};
const CATEGORY_REQUIRES_POSTER = ["event", "initiative", "merch"];
const CATEGORY_REQUIRES_DOC = ["event", "merch"];
const CATEGORY_REQUIRES_BLAST = ["event", "initiative"];
const CATEGORY_REQUIRES_EVENT_DATE = ["event", "initiative", "pantry_cleaning"];

function categoryOptions(selected) {
  return Object.entries(CATEGORY_LABELS)
    .map(([value, label]) => `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`)
    .join("");
}

// Shared by the new-proposal and edit forms: shows/hides the poster field and updates
// each requirement hint based on the selected category.
function applyCategoryRequirements(root, categoryValue) {
  const needsPoster = CATEGORY_REQUIRES_POSTER.includes(categoryValue);
  const needsDoc = CATEGORY_REQUIRES_DOC.includes(categoryValue);
  const needsBlast = CATEGORY_REQUIRES_BLAST.includes(categoryValue);
  const needsEventDate = CATEGORY_REQUIRES_EVENT_DATE.includes(categoryValue);

  const posterField = root.querySelector("[data-poster-field]");
  if (posterField) posterField.style.display = needsPoster ? "block" : "none";

  const docHint = root.querySelector("[data-doc-hint]");
  if (docHint) docHint.textContent = needsDoc ? "(required for this category)" : "(optional)";

  const blastLabel = root.querySelector("[data-blast-label]");
  if (blastLabel) {
    blastLabel.innerHTML = `Blast message ${
      needsBlast ? '<span class="field-hint">(required for this category)</span>' : "(optional)"
    }`;
  }

  const eventDateHint = root.querySelector("[data-event-date-hint]");
  if (eventDateHint) eventDateHint.textContent = needsEventDate ? "(required for this category)" : "(optional)";

  return { needsPoster, needsDoc, needsBlast, needsEventDate };
}

export function renderNewProposal(root, navigate) {
  const saved = {};
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
          ${categoryOptions(saved.category || "pantry_cleaning")}
        </select>
      </div>
      <div class="field">
        <label for="description">Description</label>
        <textarea id="description" name="description">${escapeHtml(saved.description)}</textarea>
      </div>
      <div class="field">
        <label for="event_date">Event date <span data-event-date-hint></span></label>
        <input type="date" id="event_date" name="event_date" value="${escapeHtml(saved.event_date)}" />
      </div>
      <div class="field">
        <label for="doc_link">Link / PDF URL <span data-doc-hint></span></label>
        <input type="url" id="doc_link" name="doc_link" placeholder="https://" value="${escapeHtml(saved.doc_link)}" />
      </div>
      <div class="field" data-poster-field>
        <label for="poster">Poster <span class="field-hint">Required for Event, Initiative, and Merch</span></label>
        <input type="file" id="poster" name="poster" accept="image/jpeg,image/png,image/webp,application/pdf" />
      </div>
      <div class="field">
        <label for="blast_message" data-blast-label>Blast message (optional)</label>
        <textarea id="blast_message" name="blast_message" placeholder="Message to accompany the event announcement">${escapeHtml(saved.blast_message)}</textarea>
      </div>
      <div id="form-error"></div>
      <div class="btn-row"><button type="button" class="btn btn-secondary" id="save-draft">Save Draft</button><button type="submit" class="btn">Submit for Review</button></div>
    </form>
  `;

  const form = root.querySelector("#proposal-form");
  const category = root.querySelector("#category");
  category.addEventListener("change", () => applyCategoryRequirements(root, category.value));
  applyCategoryRequirements(root, category.value);

  root.querySelector("#save-draft").addEventListener("click", async () => {
    const saveButton = root.querySelector("#save-draft");
    saveButton.disabled = true;
    try {
      const proposal = await api.post("/api/proposals", {
        title: form.title.value.trim() || "Untitled draft",
        category: form.category.value,
        description: form.description.value.trim() || null,
        event_date: form.event_date.value || null,
        doc_link: form.doc_link.value.trim() || null,
        blast_message: form.blast_message.value.trim() || null,
        save_draft: true,
      });
      const poster = form.poster.files[0];
      if (poster) {
        const formData = new FormData();
        formData.append("poster", poster);
        await api.upload(`/api/proposals/${proposal.id}/poster`, formData);
      }
      navigate("home");
    } catch (err) {
      root.querySelector("#form-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
      saveButton.disabled = false;
    }
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
      if (CATEGORY_REQUIRES_EVENT_DATE.includes(categoryValue) && !e.target.event_date.value) {
        throw new Error("Please provide an event date for this category.");
      }
      if (CATEGORY_REQUIRES_POSTER.includes(categoryValue) && !poster) {
        throw new Error("Please select a poster for this category.");
      }
      if (CATEGORY_REQUIRES_DOC.includes(categoryValue) && !e.target.doc_link.value.trim()) {
        throw new Error("Please provide a link or PDF URL for this category.");
      }
      if (CATEGORY_REQUIRES_BLAST.includes(categoryValue) && !e.target.blast_message.value.trim()) {
        throw new Error("Please provide a blast message for this category.");
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
      }
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
  const proposal = await api.get(`/api/proposals/${proposalId}`);

  const isAdmin = user.role === "admin";
  const isOwner = proposal.submitted_by === user.id;
  const canEdit = isOwner && ["draft", "needs_action"].includes(proposal.status);
  const nextStatus = NEXT_STATUS[proposal.status];
  // Owner submits a fresh draft, and resubmits after being sent back to needs_action —
  // both land on in_review. Every other status change is admin-only.
  const canOwnerSubmit = isOwner && ["draft", "needs_action"].includes(proposal.status);
  const adminHasAction = isAdmin && ["in_review", "submitted"].includes(proposal.status);

  root.innerHTML = `
    <div class="page-header">
      <span class="back" data-nav="${isAdmin ? "admin" : "home"}">&larr; Back</span>
      ${statusBadge(proposal.status)}
    </div>

    <h1>${escapeHtml(proposal.title)}</h1>
    <p>${escapeHtml(proposal.committee_name)} · Submitted by ${escapeHtml(proposal.submitter_name || "")}</p>

    <div class="card"><h3>Category</h3><p style="color:var(--text)">${escapeHtml(proposal.category.replaceAll("_", " "))}</p>
      ${proposal.blast_message ? `<h3>Blast message</h3><p style="color:var(--text); white-space:pre-wrap;">${escapeHtml(proposal.blast_message)}</p>` : ""}
      ${proposal.poster_filename ? `<div class="poster-actions">
        <span class="field-hint">Poster: ${escapeHtml(proposal.poster_filename)}</span>
        <button class="btn btn-secondary" type="button" data-poster-view>View poster</button>
        <button class="btn btn-secondary" type="button" data-poster-download>Download poster</button>
      </div>` : ""}
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
      // Only shown alongside an actual admin action button below — otherwise it's a
      // dead field with nothing to attach the note to.
      adminHasAction
        ? `<div class="field" style="margin-top:16px">
             <label for="status-comment">Note to submitter (optional)</label>
             <textarea id="status-comment" placeholder="Explain what needs to change, or add context…"></textarea>
           </div>`
        : ""
    }
    ${
      // Submitting/resubmitting is the owner's action; advancing past in_review is
      // the admin's call — never show the other party a button for a step that isn't theirs.
      (canOwnerSubmit || adminHasAction) && nextStatus
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
  `;

  renderDisposableSection(root.querySelector("#disposable-slot"), user, proposal);
  if (proposal.status === "in_review") renderEmailSection(root, user, proposal, navigate);

  const posterPath = `/api/proposals/${proposal.id}/poster`;
  root.querySelector("[data-poster-view]")?.addEventListener("click", async (e) => {
    // Open synchronously so browsers and Telegram WebView don't block the new tab.
    const preview = window.open("", "_blank");
    e.target.disabled = true;
    try {
      const { blob } = await api.getBlob(posterPath);
      const url = URL.createObjectURL(blob);
      if (preview) preview.location = url;
      else window.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      preview?.close();
      root.querySelector("#detail-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    } finally {
      e.target.disabled = false;
    }
  });
  root.querySelector("[data-poster-download]")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    try {
      const { blob, filename } = await api.getBlob(posterPath);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      root.querySelector("#detail-error").innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    } finally {
      e.target.disabled = false;
    }
  });

  root.querySelector("#advance-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, nextStatus);
  });
  root.querySelector("#revert-btn")?.addEventListener("click", async (e) => {
    await changeStatus(e.target, "needs_action");
  });
  root.querySelector("#edit-btn")?.addEventListener("click", () => {
    renderEditForm(root.querySelector("#edit-form-slot"), proposal, navigate);
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
    <form id="edit-form" class="card" style="margin-top:16px">
      <div class="field">
        <label for="e-category">Category</label>
        <select id="e-category">${categoryOptions(proposal.category)}</select>
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
        <label for="e-event_date">Event date <span data-event-date-hint></span></label>
        <input type="date" id="e-event_date" value="${proposal.event_date || ""}" />
      </div>
      <div class="field">
        <label for="e-doc_link">Link / PDF URL <span data-doc-hint></span></label>
        <input type="url" id="e-doc_link" value="${escapeHtml(proposal.doc_link)}" placeholder="https://" />
      </div>
      <div class="field" data-poster-field>
        <label for="e-poster">Poster <span class="field-hint">Required for Event, Initiative, and Merch</span></label>
        ${
          proposal.poster_filename
            ? `<p class="field-hint">Current: ${escapeHtml(proposal.poster_filename)} — choose a file below to replace it.</p>`
            : ""
        }
        <input type="file" id="e-poster" accept="image/jpeg,image/png,image/webp,application/pdf" />
      </div>
      <div class="field">
        <label for="e-blast_message" data-blast-label>Blast message</label>
        <textarea id="e-blast_message">${escapeHtml(proposal.blast_message)}</textarea>
      </div>
      <div id="edit-error"></div>
      <div class="btn-row">
        <button type="button" class="btn btn-secondary" id="edit-cancel">Cancel</button>
        <button type="submit" class="btn">Save Changes</button>
      </div>
    </form>
  `;

  const form = slot.querySelector("#edit-form");
  const category = slot.querySelector("#e-category");
  category.addEventListener("change", () => applyCategoryRequirements(slot, category.value));
  applyCategoryRequirements(slot, category.value);

  slot.querySelector("#edit-cancel").addEventListener("click", () => {
    slot.innerHTML = "";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = slot.querySelector("#edit-error");
    errorEl.innerHTML = "";
    const categoryValue = category.value;
    const poster = slot.querySelector("#e-poster").files[0];
    const hasExistingPoster = Boolean(proposal.poster_filename);

    if (CATEGORY_REQUIRES_EVENT_DATE.includes(categoryValue) && !slot.querySelector("#e-event_date").value) {
      errorEl.innerHTML = `<div class="error-banner">Please provide an event date for this category.</div>`;
      return;
    }
    if (CATEGORY_REQUIRES_POSTER.includes(categoryValue) && !poster && !hasExistingPoster) {
      errorEl.innerHTML = `<div class="error-banner">Please select a poster for this category.</div>`;
      return;
    }
    if (CATEGORY_REQUIRES_DOC.includes(categoryValue) && !slot.querySelector("#e-doc_link").value.trim()) {
      errorEl.innerHTML = `<div class="error-banner">Please provide a link or PDF URL for this category.</div>`;
      return;
    }
    if (CATEGORY_REQUIRES_BLAST.includes(categoryValue) && !slot.querySelector("#e-blast_message").value.trim()) {
      errorEl.innerHTML = `<div class="error-banner">Please provide a blast message for this category.</div>`;
      return;
    }

    try {
      await api.patch(`/api/proposals/${proposal.id}`, {
        category: categoryValue,
        title: slot.querySelector("#e-title").value.trim(),
        description: slot.querySelector("#e-description").value.trim() || null,
        event_date: slot.querySelector("#e-event_date").value || null,
        doc_link: slot.querySelector("#e-doc_link").value.trim() || null,
        blast_message: slot.querySelector("#e-blast_message").value.trim() || null,
      });
      if (poster) {
        const formData = new FormData();
        formData.append("poster", poster);
        await api.upload(`/api/proposals/${proposal.id}/poster`, formData);
      }
      navigate(`proposal/${proposal.id}`);
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
