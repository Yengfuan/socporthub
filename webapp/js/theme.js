(() => {
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = null;
  try { preference = localStorage.getItem("sph-theme"); } catch { /* Storage may be unavailable. */ }
  if (!["dark", "light"].includes(preference)) preference = null;

  function applyTheme() {
    const theme = preference || (window.Telegram?.WebApp?.colorScheme ?? (systemTheme.matches ? "dark" : "light"));
    document.documentElement.dataset.theme = theme;
    const button = document.getElementById("theme-toggle");
    if (button) {
      button.textContent = theme === "dark" ? "☀ Light mode" : "☾ Dark mode";
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} mode`);
    }
  }

  applyTheme();
  systemTheme.addEventListener("change", applyTheme);
  window.addEventListener("storage", (event) => {
    if (event.key === "sph-theme" || event.key === null) {
      preference = ["dark", "light"].includes(event.newValue) ? event.newValue : null;
      applyTheme();
    }
  });
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme();
    window.Telegram?.WebApp?.onEvent("themeChanged", applyTheme);
    document.getElementById("theme-toggle").addEventListener("click", () => {
      preference = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try { localStorage.setItem("sph-theme", preference); } catch { /* Still switch for this visit. */ }
      applyTheme();
    });
  });
})();
