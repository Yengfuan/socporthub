const TABS = [
  { route: "home", label: "Home" },
  { route: "calendar", label: "Calendar" },
  { route: "reminders", label: "Reminders" },
];

export function renderBottomNav(activeRoute, reminderCount = 0) {
  return `
    <div class="bottom-nav">
      ${TABS.map(
        (t) =>
          `<a href="#" data-nav="${t.route}" class="${activeRoute === t.route ? "active" : ""}">${t.label}${t.route === "reminders" && reminderCount ? ` <span class="nav-badge">${reminderCount}</span>` : ""}</a>`
      ).join("")}
    </div>
  `;
}
