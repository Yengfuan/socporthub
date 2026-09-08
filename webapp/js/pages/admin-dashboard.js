import { api } from "../api.js";
import { statusBadge } from "../components/status-badge.js";
import { proposalCard } from "../components/proposal-card.js";

const STATUS_LABELS = {
  draft: "Drafts",
  needs_action: "Needs Action",
  in_review: "In Review",
  submitted: "Submitted",
  finished: "Finished",
};

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

export async function renderAdminDashboard(root, tab = "proposals") {
  root.innerHTML = `
    <h1>Admin Dashboard</h1>
    <div class="chip-row" id="section-tabs">
      <div class="chip ${tab === "proposals" ? "active" : ""}" data-tab="proposals">Proposals</div>
      <div class="chip ${tab === "disposables" ? "active" : ""}" data-tab="disposables">Disposables</div>
      <div class="chip ${tab === "users" ? "active" : ""}" data-tab="users">Users</div>
    </div>
    <div id="section-content"><div class="loading">Loading…</div></div>
  `;

  root.querySelectorAll("#section-tabs .chip").forEach((chip) => {
    chip.addEventListener("click", () => renderAdminDashboard(root, chip.dataset.tab));
  });

  const content = root.querySelector("#section-content");
  if (tab === "users") {
    await renderUsersSection(content);
  } else if (tab === "disposables") {
    await renderDisposablesSection(content);
  } else {
    await renderProposalsSection(content);
  }
}

async function renderDisposablesSection(content) {
  const requests = await api.get("/api/disposables");
  const todayStr = new Date().toISOString().slice(0, 10);

  const byDate = new Map();
  for (const r of requests) {
    if (!byDate.has(r.collection_date)) byDate.set(r.collection_date, []);
    byDate.get(r.collection_date).push(r);
  }
  const dates = Array.from(byDate.keys()).sort();

  if (!dates.length) {
    content.innerHTML = `<div class="empty-state"><div class="icon">🍽️</div><p>No disposable requests yet.</p></div>`;
    return;
  }

  content.innerHTML = dates
    .map((d) => {
      const items = byDate.get(d);
      const totals = items.reduce(
        (acc, r) => ({
          plates: acc.plates + r.plates,
          cups: acc.cups + r.cups,
          forks: acc.forks + r.forks,
          spoons: acc.spoons + r.spoons,
        }),
        { plates: 0, cups: 0, forks: 0, spoons: 0 }
      );
      const isToday = d === todayStr;
      return `
        <div class="card" style="${isToday ? "border: 2px solid var(--accent);" : ""}">
          <h3>${d}${isToday ? " · Today" : ""}</h3>
          <p style="color:var(--text)">Totals — Plates: ${totals.plates} · Cups: ${totals.cups} · Forks: ${totals.forks} · Spoons: ${totals.spoons}</p>
          ${items
            .map(
              (r) => `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-top:1px solid var(--border);">
              <div>
                <div style="font-size:13px; font-weight:600;">${escapeHtml(r.proposal_title)}</div>
                <div style="font-size:12px; color:var(--text-muted)">${escapeHtml(r.committee_name)} · ${escapeHtml(r.requester_name || "")}</div>
              </div>
              ${
                r.approved
                  ? `<span class="badge badge-approved">Approved</span>`
                  : `<button class="btn" style="width:auto; padding:6px 14px;" data-approve-disposable="${r.id}">Approve</button>`
              }
            </div>`
            )
            .join("")}
        </div>
      `;
    })
    .join("");

  content.querySelectorAll("[data-approve-disposable]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      await api.patch(`/api/disposables/${btn.dataset.approveDisposable}`, { approved: true });
      renderDisposablesSection(content);
    });
  });
}

async function renderProposalsSection(content, committeeId = null) {
  const committees = await api.get("/api/committees");
  const query = committeeId ? `?committee_id=${committeeId}` : "";
  const [summary, proposals] = await Promise.all([
    api.get(`/api/proposals/summary${query}`),
    api.get(`/api/proposals${query}`),
  ]);

  content.innerHTML = `
    <div class="chip-row">
      <div class="chip ${!committeeId ? "active" : ""}" data-committee="">All</div>
      ${committees
        .map((c) => `<div class="chip ${committeeId == c.id ? "active" : ""}" data-committee="${c.id}">${escapeHtml(c.name)}</div>`)
        .join("")}
    </div>

    <div class="summary-grid">
      ${Object.entries(STATUS_LABELS)
        .map(([key, label]) => `<div class="summary-card"><div class="count">${summary[key] ?? 0}</div><div class="label">${label}</div></div>`)
        .join("")}
    </div>

    <h2>Proposals</h2>
    ${
      proposals.length
        ? proposals.map((p) => proposalCard(p, { showCommittee: !committeeId })).join("")
        : `<div class="empty-state"><div class="icon">📋</div><p>No proposals in this view.</p></div>`
    }
  `;

  content.querySelectorAll("[data-committee]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const id = chip.dataset.committee || null;
      renderProposalsSection(content, id);
    });
  });
}

async function renderUsersSection(content) {
  const [users, committees] = await Promise.all([
    api.get("/api/admin/users"),
    api.get("/api/committees"),
  ]);

  const pending = users.filter((u) => u.status === "pending");
  const others = users.filter((u) => u.status !== "pending");

  content.innerHTML = `
    ${pending.length ? `<h2>Pending approval (${pending.length})</h2>` : ""}
    ${pending.map((u) => userRow(u, committees, { pendingActions: true })).join("")}
    <h2>All users</h2>
    ${others.map((u) => userRow(u, committees, { pendingActions: false })).join("")}
  `;

  content.querySelectorAll("[data-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api.patch(`/api/admin/users/${btn.dataset.approve}`, { status: "approved" });
      renderUsersSection(content);
    });
  });
  content.querySelectorAll("[data-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api.patch(`/api/admin/users/${btn.dataset.reject}`, { status: "rejected" });
      renderUsersSection(content);
    });
  });
  content.querySelectorAll("[data-save-committees]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const userId = btn.dataset.saveCommittees;
      const checked = Array.from(
        content.querySelectorAll(`input[data-user="${userId}"]:checked`)
      ).map((i) => Number(i.value));
      btn.disabled = true;
      btn.textContent = "Saving…";
      await api.patch(`/api/admin/users/${userId}`, { committee_ids: checked });
      renderUsersSection(content);
    });
  });
}

function userRow(user, committees, { pendingActions }) {
  const memberIds = new Set(user.committees.map((c) => c.id));
  return `
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div class="title">${escapeHtml(user.display_name || user.email)}</div>
          <div style="font-size:12px; color:var(--text-muted)">${escapeHtml(user.email)}</div>
        </div>
        ${statusBadge(user.status)}
      </div>

      ${
        pendingActions
          ? `<div class="btn-row" style="margin-top:12px">
               <button class="btn" data-approve="${user.id}">Approve</button>
               <button class="btn btn-secondary" data-reject="${user.id}">Reject</button>
             </div>`
          : user.role !== "admin"
          ? `<div style="margin-top:12px">
               <div class="field-hint" style="margin-bottom:6px">Committees</div>
               ${committees
                 .map(
                   (c) => `
                 <label style="display:flex; align-items:center; gap:6px; font-size:13px; margin-bottom:4px;">
                   <input type="checkbox" data-user="${user.id}" value="${c.id}" ${
                     memberIds.has(c.id) ? "checked" : ""
                   } />
                   ${escapeHtml(c.name)}
                 </label>`
                 )
                 .join("")}
               <button class="btn btn-secondary" data-save-committees="${user.id}" style="margin-top:8px">Save Committees</button>
             </div>`
          : ""
      }
    </div>
  `;
}
