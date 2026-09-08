import { api } from "./api.js";
import { renderRegister, renderPendingOrRejected } from "./pages/register.js";
import { renderHome } from "./pages/home.js";
import { renderNewProposal, renderProposalDetail } from "./pages/proposal-detail.js";
import { renderAdminDashboard } from "./pages/admin-dashboard.js";

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const root = document.getElementById("app");
let currentUser = null;

function navigate(route) {
  window.location.hash = route;
}

function currentRoute() {
  return window.location.hash.replace(/^#\/?/, "") || "home";
}

async function render() {
  const route = currentRoute();

  if (!currentUser) {
    root.innerHTML = `<div class="loading">Loading…</div>`;
    try {
      const { registered, user } = await api.get("/api/auth/validate");
      if (!registered) {
        renderRegister(root, (user) => {
          currentUser = user;
          render();
        });
        return;
      }
      currentUser = user;
    } catch (err) {
      root.innerHTML = `<div class="error-banner">Could not verify your Telegram session: ${err.message}</div>`;
      return;
    }
  }

  if (currentUser.status !== "approved") {
    root.innerHTML = renderPendingOrRejected(currentUser);
    return;
  }

  try {
    if (route === "home") {
      if (currentUser.role === "admin") {
        await renderAdminDashboard(root);
      } else {
        await renderHome(root, currentUser);
      }
    } else if (route === "admin") {
      await renderAdminDashboard(root);
    } else if (route === "proposal/new") {
      renderNewProposal(root, navigate);
    } else if (route.startsWith("proposal/")) {
      const id = route.split("/")[1];
      await renderProposalDetail(root, currentUser, id, navigate);
    } else {
      navigate("home");
    }
  } catch (err) {
    root.innerHTML = `<div class="error-banner">${err.message}</div>`;
  }
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
