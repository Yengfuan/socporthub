import { statusBadge } from "./status-badge.js";

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

export function proposalCard(proposal, { showCommittee = false } = {}) {
  const dateStr = proposal.event_date
    ? new Date(proposal.event_date + "T00:00:00").toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
    : "No date set";

  return `
    <a class="card proposal-card" data-nav="proposal/${proposal.id}">
      <div class="title">${escapeHtml(proposal.title)}</div>
      <div class="meta">
        <span>${showCommittee ? escapeHtml(proposal.committee_name) + " · " : ""}${escapeHtml(
    proposal.submitter_name || ""
  )} · ${dateStr}</span>
        ${statusBadge(proposal.status)}
      </div>
    </a>
  `;
}
