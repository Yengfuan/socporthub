import { api } from "../api.js";

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function statusLabel(status) {
  return status === "completed" ? "Completed" : status === "opened" ? "Opened" : "Not started";
}

function storageKey(proposalId, formKey) {
  return `google-form-status:${proposalId}:${formKey}`;
}

function getStatus(proposalId, formKey) {
  return localStorage.getItem(storageKey(proposalId, formKey)) || "pending";
}

function setStatus(proposalId, formKey, status) {
  localStorage.setItem(storageKey(proposalId, formKey), status);
}

function formCard(form, proposal) {
  const status = getStatus(proposal.id, form.form_key);
  const sections = form.sections?.length
    ? `<div class="committee-form-sections"><span class="field-hint">Sections:</span> ${form.sections.map(escapeHtml).join(" · ")}</div>`
    : "";
  return `<div class="committee-form-card" data-form-card="${escapeHtml(form.form_key)}">
    <div>
      <strong>${escapeHtml(form.committee_name)}</strong>
      <div class="field-hint" data-form-status>${statusLabel(status)}</div>
      ${sections}
    </div>
    <div class="committee-form-actions">
      ${form.url
        ? `<a class="btn btn-secondary" data-open-form href="${escapeHtml(form.url)}" target="_blank" rel="noopener">Open form</a>`
        : `<button class="btn btn-secondary" type="button" disabled>Link not configured</button>`}
      <button class="btn" type="button" data-complete-form>${status === "completed" ? "Mark incomplete" : "Mark complete"}</button>
    </div>
  </div>`;
}

export async function renderCommitteeFormsSection(slot, proposal) {
  try {
    const forms = await api.get("/api/committees/forms");
    const requested = proposal.requested_ccas || [];
    const selectedForms = forms.filter((form) => requested.includes(form.form_key));
    if (!selectedForms.length) return;

    slot.innerHTML = `<div class="card committee-forms-card">
      <h3>Committee forms</h3>
      <p class="field-hint">Open each selected official form and complete it manually.</p>
      <div class="committee-form-list">${selectedForms.map((form) => formCard(form, proposal)).join("")}</div>
      <p class="field-hint">Test mode: completion is saved in this browser only.</p>
    </div>`;

    slot.querySelectorAll("[data-form-toggle]").forEach((toggle) => {
      toggle.addEventListener("change", (event) => {
        const card = Array.from(slot.querySelectorAll("[data-form-card]"))
          .find((candidate) => candidate.dataset.formCard === event.currentTarget.dataset.formToggle);
        card.hidden = !event.currentTarget.checked;
      });
    });

    slot.querySelectorAll("[data-open-form]").forEach((link) => {
      link.addEventListener("click", (event) => {
        const card = event.currentTarget.closest("[data-form-card]");
        setStatus(proposal.id, card.dataset.formCard, "opened");
        card.querySelector("[data-form-status]").textContent = "Opened";
      });
    });
    slot.querySelectorAll("[data-complete-form]").forEach((button) => {
      button.addEventListener("click", (event) => {
        const card = event.currentTarget.closest("[data-form-card]");
        const id = card.dataset.formCard;
        const next = getStatus(proposal.id, id) === "completed" ? "opened" : "completed";
        setStatus(proposal.id, id, next);
        card.querySelector("[data-form-status]").textContent = statusLabel(next);
        button.textContent = next === "completed" ? "Mark incomplete" : "Mark complete";
      });
    });
  } catch (error) {
    slot.innerHTML = `<div class="error-banner">Could not load committee forms: ${escapeHtml(error.message)}</div>`;
  }
}
