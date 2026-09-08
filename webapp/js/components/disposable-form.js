import { api } from "../api.js";

export async function renderDisposableSection(container, user, proposal) {
  const isAdmin = user.role === "admin";
  const isOwner = proposal.submitted_by === user.id;
  if (!isAdmin && !isOwner) {
    container.innerHTML = "";
    return;
  }

  const existing = (await api.get(`/api/disposables?proposal_id=${proposal.id}`))[0] || null;
  const canEdit = isOwner && !(existing && existing.approved);

  container.innerHTML = `
    <div class="card">
      <h3>Hall Disposables</h3>
      ${
        existing
          ? `<p style="color:var(--text)">
               Plates: ${existing.plates} · Cups: ${existing.cups} · Forks: ${existing.forks} · Spoons: ${existing.spoons}<br/>
               Collection date: ${existing.collection_date}
             </p>
             <span class="badge ${existing.approved ? "badge-approved" : "badge-pending"}">
               ${existing.approved ? "Approved" : "Pending approval"}
             </span>`
          : `<p>No disposables requested for this proposal yet.</p>`
      }

      ${isAdmin && existing && !existing.approved ? `<button class="btn" id="approve-disposable" style="margin-top:12px">Approve</button>` : ""}
      ${canEdit ? `<button class="btn btn-secondary" id="edit-disposable" style="margin-top:12px">${existing ? "Edit Request" : "Request Disposables"}</button>` : ""}
      <div id="disposable-form-slot"></div>
    </div>
  `;

  container.querySelector("#approve-disposable")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    await api.patch(`/api/disposables/${existing.id}`, { approved: true });
    renderDisposableSection(container, user, proposal);
  });

  container.querySelector("#edit-disposable")?.addEventListener("click", () => {
    renderForm(container.querySelector("#disposable-form-slot"), proposal, existing, () =>
      renderDisposableSection(container, user, proposal)
    );
  });
}

function renderForm(slot, proposal, existing, onSaved) {
  slot.innerHTML = `
    <form id="disposable-form" style="margin-top:12px">
      <div class="field">
        <label for="d-plates">Plates</label>
        <input type="number" id="d-plates" min="0" value="${existing?.plates ?? 0}" />
      </div>
      <div class="field">
        <label for="d-cups">Cups</label>
        <input type="number" id="d-cups" min="0" value="${existing?.cups ?? 0}" />
      </div>
      <div class="field">
        <label for="d-forks">Forks</label>
        <input type="number" id="d-forks" min="0" value="${existing?.forks ?? 0}" />
      </div>
      <div class="field">
        <label for="d-spoons">Spoons</label>
        <input type="number" id="d-spoons" min="0" value="${existing?.spoons ?? 0}" />
      </div>
      <div class="field">
        <label for="d-collection_date">Collection date</label>
        <input type="date" id="d-collection_date" value="${existing?.collection_date ?? ""}" required />
      </div>
      <div id="disposable-error"></div>
      <button type="submit" class="btn">Save Request</button>
    </form>
  `;

  slot.querySelector("#disposable-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = slot.querySelector("#disposable-error");
    try {
      await api.post(`/api/disposables/${proposal.id}`, {
        plates: Number(slot.querySelector("#d-plates").value) || 0,
        cups: Number(slot.querySelector("#d-cups").value) || 0,
        forks: Number(slot.querySelector("#d-forks").value) || 0,
        spoons: Number(slot.querySelector("#d-spoons").value) || 0,
        collection_date: slot.querySelector("#d-collection_date").value,
      });
      onSaved();
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
