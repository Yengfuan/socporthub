import { api } from "../api.js";
import { proposalCard } from "../components/proposal-card.js";

const STATUS_LABELS = {
  draft: "Drafts",
  needs_action: "Needs Action",
  in_review: "In Review",
  submitted: "Submitted",
  finished: "Finished",
  grading: "Grading",
  final: "Final",
};

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

export async function renderHome(root, user) {
  root.innerHTML = `<div class="loading">Loading…</div>`;

  const [summary, proposals] = await Promise.all([
    api.get("/api/proposals/summary"),
    api.get("/api/proposals"),
  ]);

  const committeeNames = escapeHtml((user.committees || []).map((c) => c.name).join(", ") || "No committee assigned yet");

  root.innerHTML = `
    <div class="page-header">
      <h1>Hi, ${escapeHtml(user.display_name || user.email)}</h1>
    </div>

    <div class="card" style="padding:10px 16px; display:flex; align-items:center; gap:8px;">
      <span style="font-size:12px; color:var(--text-muted);">Committee</span>
      <span style="font-size:13px; font-weight:600;">${committeeNames}</span>
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

    ${proposals.some((p) => p.status === "grading" && p.submitted_by === user.id) ? `<div class="grading-deadline"><strong>Self-assessments need your attention</strong><span>Open a proposal marked Grading to see its deadline, save scores, and submit.</span></div>` : ""}
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
