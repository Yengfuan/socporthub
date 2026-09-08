const TABS = [
  { route: "home", label: "Home" },
  { route: "calendar", label: "Calendar" },
];

export function renderBottomNav(activeRoute) {
  return `
    <div class="bottom-nav">
      ${TABS.map(
        (t) =>
          `<a href="#" data-nav="${t.route}" class="${activeRoute === t.route ? "active" : ""}">${t.label}</a>`
      ).join("")}
    </div>
  `;
}
