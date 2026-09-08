const LABELS = {
  needs_action: "Needs Action",
  in_review: "In Review",
  submitted: "Submitted",
  finished: "Finished",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export function statusBadge(status) {
  const label = LABELS[status] || status;
  return `<span class="badge badge-${status}">${label}</span>`;
}
