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

function fieldInput(fieldKey, field, values = {}) {
  const type = ["text", "date", "time", "number", "email", "url"].includes(field.type) ? field.type : "text";
  const value = values[fieldKey] ?? field.value ?? "";
  const isManual = field.source === "manual";
  const label = `${escapeHtml(field.label)}${!isManual ? " (auto-filled)" : ""}${field.required ? " *" : ""}`;
  const options = field.options?.length
    ? field.options.map((option) => `<option value="${escapeHtml(option)}" ${value === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")
    : "";
  const control = options
    ? `<select data-external-field="${escapeHtml(fieldKey)}" ${!isManual ? "disabled" : ""}>${options}</select>`
    : `<input type="${type}" data-external-field="${escapeHtml(fieldKey)}" value="${escapeHtml(value)}" ${isManual && field.required ? "required" : ""} ${!isManual ? "readonly" : ""} />`;
  return `<div class="field"><label>${label}</label>${control}</div>`;
}

export async function loadCommitteeFormFields(root, proposal = null) {
  const forms = await api.get("/api/committees/forms");
  const byKey = new Map(forms.map((form) => [form.form_key, form]));
  root.querySelectorAll(".cca-request-panel").forEach((panel) => {
    const form = byKey.get(panel.dataset.cca);
    if (!form || !Object.keys(form.fields || {}).length) return;
    const values = proposal?.external_form_data?.[form.form_key] || {};
    const manualFields = Object.entries(form.fields).filter(([, field]) => field.source === "manual");
    panel.querySelector(".cca-request-fields").innerHTML = manualFields.length
      ? manualFields.map(([key, field]) => fieldInput(key, field, values)).join("")
      : `<span class="field-hint">No additional information is needed here. Automatically mapped fields will be added when the form opens.</span>`;
  });
}

export function collectExternalFormData(root) {
  const data = {};
  root.querySelectorAll(".cca-request-panel").forEach((panel) => {
    const values = {};
    panel.querySelectorAll("[data-external-field]").forEach((input) => {
      values[input.dataset.externalField] = input.value;
    });
    if (Object.keys(values).length) data[panel.dataset.cca] = values;
  });
  return data;
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
        ? `<a class="btn btn-secondary" data-open-form href="${escapeHtml(prefilledUrl(form, proposal))}" target="_blank" rel="noopener">Open form</a>`
        : `<button class="btn btn-secondary" type="button" disabled>Link not configured</button>`}
      <button class="btn" type="button" data-complete-form>${status === "completed" ? "Mark incomplete" : "Mark complete"}</button>
    </div>
  </div>`;
}

function prefilledUrl(form, proposal) {
  const url = new URL(form.url);
  url.searchParams.set("usp", "pp_url");
  const stored = proposal.external_form_data?.[form.form_key] || {};
  const sourceValues = {
    title: proposal.title,
    event_name: proposal.title,
    description: proposal.description || "",
    event_date: proposal.event_date || "",
    event_time: proposal.event_time || "",
    doc_link: proposal.doc_link || "",
    committee_and_category: `${proposal.committee_name} - ${proposal.category.replaceAll("_", " ")}`,
    constant: null,
    submitter_name: proposal.submitter_name || "",
    person_in_charge: proposal.submitter_name || "",
    committee_name: form.committee_name,
    request_id: String(proposal.id),
  };
  Object.entries(form.fields || {}).forEach(([key, field]) => {
    const value = field.source === "constant"
      ? field.value
      : field.source && field.source !== "manual" ? sourceValues[field.source] : stored[key];
    if (field.entry_id && value !== undefined && value !== "") url.searchParams.set(field.entry_id, value);
  });
  return url.toString();
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
