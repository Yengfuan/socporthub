import { api } from "./api.js";
import { renderRegister, renderPendingOrRejected } from "./pages/register.js";
import { renderHome } from "./pages/home.js";
import { renderNewProposal, renderProposalDetail } from "./pages/proposal-detail.js";
import { renderAdminDashboard } from "./pages/admin-dashboard.js";
import { renderCalendar } from "./pages/calendar.js";
import { renderReminders } from "./pages/reminders.js";
import { renderBugReport } from "./pages/bug-report.js";
import { renderBottomNav } from "./components/nav.js";

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const app = document.getElementById("app");
let currentUser = null;

const TOP_LEVEL_ROUTES = new Set(["home", "admin", "calendar", "reminders", "bug-report"]);

function navigate(route) {
  window.location.hash = route;
}

function currentRoute() {
  return window.location.hash.replace(/^#\/?/, "") || "home";
}

async function setNav(activeRoute) {
  let nav = app.querySelector(".bottom-nav");
  if (!TOP_LEVEL_ROUTES.has(activeRoute)) {
    nav?.remove();
    return;
  }
  const navRoute = activeRoute === "admin" ? "home" : activeRoute;
  let reminderCount = 0;
  if (currentUser?.role === "admin") {
    try { reminderCount = (await api.get("/api/reminders/unread-count")).count; } catch { /* keep nav usable */ }
  }
  const html = renderBottomNav(navRoute, reminderCount);
  if (nav) {
    nav.outerHTML = html;
  } else {
    app.insertAdjacentHTML("beforeend", html);
  }
}

async function render() {
  const route = currentRoute();

  if (!currentUser) {
    app.innerHTML = `<div class="loading">Loading…</div>`;
    try {
      const { registered, user } = await api.post("/api/auth/validate");
      if (!registered) {
        renderRegister(app, (user) => {
          currentUser = user;
          render();
        });
        return;
      }
      currentUser = user;
    } catch (err) {
      app.innerHTML = `<div class="error-banner">Could not verify your Telegram session: ${err.message}</div>`;
      return;
    }
  }

  if (currentUser.status !== "approved") {
    app.innerHTML = renderPendingOrRejected(currentUser);
    return;
  }

  app.innerHTML = `<div id="page-content"></div>`;
  const page = app.querySelector("#page-content");

  try {
    if (route === "home") {
      if (currentUser.role === "admin") {
        await renderAdminDashboard(page);
      } else {
        await renderHome(page, currentUser);
      }
    } else if (route === "admin") {
      await renderAdminDashboard(page);
    } else if (route === "calendar") {
      await renderCalendar(page, currentUser);
    } else if (route === "reminders") {
      await renderReminders(page, currentUser);
    } else if (route === "bug-report") {
      renderBugReport(page);
    } else if (route === "proposal/new") {
      renderNewProposal(page, navigate, currentUser);
    } else if (route.startsWith("proposal/")) {
      const id = route.split("/")[1];
      await renderProposalDetail(page, currentUser, id, navigate);
    } else {
      navigate("home");
      return;
    }
  } catch (err) {
    page.innerHTML = `<div class="error-banner">${err.message}</div>`;
  }

  await setNav(route);
}

// Delegate clicks on any [data-nav] element to the hash router.
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-nav]");
  if (!el) return;
  e.preventDefault();
  navigate(el.dataset.nav);
});

window.addEventListener("hashchange", render);
render();
