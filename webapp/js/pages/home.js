import { api } from "../api.js";
import { proposalCard } from "../components/proposal-card.js";

const STATUS_LABELS = {
  needs_action: "Needs Action",
  in_review: "In Review",
  submitted: "Submitted",
  finished: "Finished",
};

export async function renderHome(root, user) {
  root.innerHTML = `<div class="loading">Loading…</div>`;

  const [summary, proposals] = await Promise.all([
    api.get("/api/proposals/summary"),
    api.get("/api/proposals"),
  ]);

  root.innerHTML = `
    <div class="page-header">
      <h1>Hi, ${user.display_name || user.email}</h1>
    </div>

    <div class="summary-grid">
      ${Object.entries(STATUS_LABELS)
        .map(
          ([key, label]) => `
        <div class="summary-card">
          <div class="count">${summary[key] ?? 0}</div>
          <div class="label">${label}</div>
        </div>`
        )
        .join("")}
    </div>

    <h2>Recent proposals</h2>
    <div id="proposal-list">
      ${
        proposals.length
          ? proposals.map((p) => proposalCard(p)).join("")
          : `<div class="empty-state"><div class="icon">📋</div><p>No proposals yet — submit one to get started.</p></div>`
      }
    </div>

    <div class="fab">
      <a class="btn" data-nav="proposal/new">+ New Proposal</a>
    </div>
  `;
}
