import { api } from "../api.js";

const DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

const ICON_WARNING = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>`;
const ICON_CALENDAR_PLUS = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M12 14v4M10 16h4"/></svg>`;

// A popup with a × button. Closes on ×, a click outside the panel, or Escape.
// Returns the body element for the caller to fill.
function openModal(title) {
  document.querySelector(".cal-modal")?.remove();
  const modal = document.createElement("div");
  modal.className = "cal-modal";
  modal.innerHTML = `
    <div class="cal-modal-backdrop" data-modal-close></div>
    <div class="cal-modal-panel" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
      <div class="cal-modal-header">
        <h3>${escapeHtml(title)}</h3>
        <button type="button" class="cal-modal-close" data-modal-close aria-label="Close">&times;</button>
      </div>
      <div class="cal-modal-body"></div>
    </div>`;
  const close = () => {
    modal.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => {
    if (e.key === "Escape") close();
  };
  modal.querySelectorAll("[data-modal-close]").forEach((el) => el.addEventListener("click", close));
  document.addEventListener("keydown", onKey);
  document.body.appendChild(modal);
  modal.querySelector(".cal-modal-close").focus();
  return modal.querySelector(".cal-modal-body");
}

function toISODate(d) {
  return d.toISOString().slice(0, 10);
}

function gridRange(year, month) {
  // month is 0-indexed. Returns the Sunday-aligned start/end covering the full grid.
  const first = new Date(Date.UTC(year, month, 1));
  const last = new Date(Date.UTC(year, month + 1, 0));
  const start = new Date(first);
  start.setUTCDate(start.getUTCDate() - start.getUTCDay());
  const end = new Date(last);
  end.setUTCDate(end.getUTCDate() + (6 - end.getUTCDay()));
  return { start, end, first, last };
}

export async function renderCalendar(root, user, state = {}) {
  const today = new Date();
  const year = state.year ?? today.getUTCFullYear();
  const month = state.month ?? today.getUTCMonth();
  const committeeId = state.committeeId ?? null;
  const selectedDate = state.selectedDate ?? null;
  const addingEvent = state.addingEvent ?? false;
  const isAdmin = user.role === "admin";

  root.innerHTML = `<div class="loading">Loading…</div>`;

  const [committees, events, feed] = await Promise.all([
    api.get("/api/committees"),
    fetchEvents(year, month, committeeId),
    api.get("/api/calendar/feed-url").catch(() => null),
  ]);

  const { start, end, first, last } = gridRange(year, month);
  const eventsByDate = groupByDate(events, (e) => e.date);

  const monthLabel = first.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });

  const cells = [];
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    const iso = toISODate(d);
    const inMonth = d >= first && d <= last;
    const isToday = iso === toISODate(today);
    const dayEvents = eventsByDate.get(iso) || [];
    const hasBlockout = dayEvents.some((e) => e.is_blockout);
    const dotEvents = dayEvents.filter((e) => !e.is_blockout);

    cells.push(`
      <div class="cal-cell ${inMonth ? "" : "cal-cell-outside"} ${isToday ? "cal-cell-today" : ""} ${
      selectedDate === iso ? "cal-cell-selected" : ""
    }" data-date="${iso}">
        <div class="cal-daynum">${d.getUTCDate()}</div>
        <div class="cal-dots">
          ${hasBlockout ? `<span class="cal-blockout" title="Block-out date" aria-label="Block-out date">&#9888;</span>` : ""}
          ${dotEvents
            .slice(0, 3)
            .map((e) => `<span class="cal-dot" style="background:${e.committee_color || "var(--text-muted)"}"></span>`)
            .join("")}
        </div>
      </div>
    `);
  }

  root.innerHTML = `
    <h1>Calendar</h1>
    <div class="cal-toolbar">
      <button type="button" class="cal-action-btn" id="cal-blockouts">${ICON_WARNING}<span>Block-out dates</span></button>
      ${
        feed
          ? `<button type="button" class="cal-action-btn" id="cal-subscribe" title="Subscribe from your phone's calendar app">${ICON_CALENDAR_PLUS}<span>Subscribe</span></button>`
          : ""
      }
    </div>

    <div class="chip-row">
      <div class="chip ${!committeeId ? "active" : ""}" data-committee="">All</div>
      ${committees
        .map(
          (c) =>
            `<div class="chip ${committeeId == c.id ? "active" : ""}" data-committee="${c.id}">${escapeHtml(c.name)}</div>`
        )
        .join("")}
    </div>

    <div class="cal-nav">
      <button type="button" class="cal-nav-btn" id="cal-prev" aria-label="Previous month">&larr; Prev</button>
      <h2>${monthLabel}</h2>
      <button type="button" class="cal-nav-btn" id="cal-next" aria-label="Next month">Next &rarr;</button>
    </div>

    <div class="cal-grid cal-grid-header">
      ${DAY_LABELS.map((l) => `<div class="cal-headcell">${l}</div>`).join("")}
    </div>
    <div class="cal-grid">${cells.join("")}</div>

    <div id="cal-day-panel" style="margin-top:16px"></div>

    ${
      isAdmin
        ? `<div class="fab">
             <a class="btn" id="cal-add-event">${addingEvent ? "Cancel" : "+ Add Event"}</a>
           </div>`
        : ""
    }
  `;

  root.querySelector("#cal-prev").addEventListener("click", () => {
    const prev = new Date(Date.UTC(year, month - 1, 1));
    renderCalendar(root, user, { year: prev.getUTCFullYear(), month: prev.getUTCMonth(), committeeId });
  });
  root.querySelector("#cal-next").addEventListener("click", () => {
    const next = new Date(Date.UTC(year, month + 1, 1));
    renderCalendar(root, user, { year: next.getUTCFullYear(), month: next.getUTCMonth(), committeeId });
  });
  root.querySelectorAll("[data-committee]").forEach((chip) => {
    chip.addEventListener("click", () => {
      renderCalendar(root, user, { year, month, committeeId: chip.dataset.committee || null, selectedDate });
    });
  });
  root.querySelectorAll(".cal-cell").forEach((cell) => {
    cell.addEventListener("click", () => {
      // Selecting a day always shows that day's view, closing any open add-event form.
      renderCalendar(root, user, { year, month, committeeId, selectedDate: cell.dataset.date });
    });
  });
  root.querySelector("#cal-subscribe")?.addEventListener("click", () => {
    renderSubscribePanel(openModal("Subscribe from your calendar app"), feed.url);
  });
  root.querySelector("#cal-blockouts").addEventListener("click", () => {
    renderBlockoutPanel(openModal("Block-out dates"));
  });
  root.querySelector("#cal-add-event")?.addEventListener("click", () => {
    renderCalendar(root, user, { year, month, committeeId, selectedDate, addingEvent: !addingEvent });
  });

  if (addingEvent) {
    renderEventForm(root.querySelector("#cal-day-panel"), user, committees, selectedDate, () =>
      renderCalendar(root, user, { year, month, committeeId, selectedDate, addingEvent: false })
    );
  } else if (selectedDate) {
    renderDayPanel(
      root.querySelector("#cal-day-panel"),
      selectedDate,
      eventsByDate.get(selectedDate) || [],
      user,
      () => renderCalendar(root, user, { year, month, committeeId, selectedDate })
    );
  }
}

async function fetchEvents(year, month, committeeId) {
  const { start, end } = gridRange(year, month);
  const query = new URLSearchParams({ start: toISODate(start), end: toISODate(end) });
  if (committeeId) query.set("committee_id", committeeId);
  return api.get(`/api/calendar?${query}`);
}

function renderSubscribePanel(panel, url) {
  panel.innerHTML = `
    <p class="cal-modal-note">Add this URL as a subscribed calendar in Google Calendar, Apple Calendar, or Outlook.
    New events show up automatically, though it may take a few hours to refresh.</p>
    <input type="text" class="cal-url-input" readonly value="${escapeHtml(url)}" onclick="this.select()" />
    <button class="btn" id="cal-copy-url">Copy link</button>
  `;
  panel.querySelector("#cal-copy-url").addEventListener("click", async (e) => {
    try {
      await navigator.clipboard.writeText(url);
      e.target.textContent = "Copied!";
      setTimeout(() => (e.target.textContent = "Copy link"), 1500);
    } catch {
      /* clipboard API unavailable; the input above is selectable as a fallback */
    }
  });
}

async function renderBlockoutPanel(panel) {
  panel.innerHTML = `<div class="loading">Loading…</div>`;
  let blockouts;
  try {
    blockouts = await api.get("/api/calendar/blockouts");
  } catch (err) {
    panel.innerHTML = `<div class="error-banner">${escapeHtml(err.message)}</div>`;
    return;
  }
  panel.innerHTML = `
    <p class="cal-modal-note">No other CCA should hold an event on these dates. A proposal on one of them is flagged for review.</p>
    ${
      blockouts.length
        ? blockouts
            .map((b) => {
              const when = new Date(b.date + "T00:00:00").toLocaleDateString(undefined, {
                weekday: "short",
                day: "numeric",
                month: "short",
                year: "numeric",
              });
              return `
        <div class="cal-blockout-row">
          <div>
            <div class="title">${escapeHtml(b.title)}</div>
            <div class="meta">${when}</div>
          </div>
          <span class="badge" style="background:${b.committee_color}20; color:${b.committee_color}">${escapeHtml(b.committee_name)}</span>
        </div>`;
            })
            .join("")
        : `<p class="cal-modal-note">No upcoming block-out dates.</p>`
    }
  `;
}

function groupByDate(items, keyFn) {
  const map = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

function renderDayPanel(panel, dateStr, events, user, refresh) {
  const isAdmin = user.role === "admin";

  panel.innerHTML = `
    <h3>${dateStr}</h3>
    ${
      events.length
        ? events
            .map(
              (e) => `
        <div class="card" data-event-id="${e.id}">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="title">${e.is_blockout ? "&#9888; " : ""}${escapeHtml(e.title)}${e.is_blockout ? " (block-out)" : ""}</div>
            <span class="badge" style="background:${e.committee_color}20; color:${e.committee_color}">${escapeHtml(e.committee_name)}</span>
          </div>
          ${e.description ? `<p>${escapeHtml(e.description)}</p>` : ""}
          ${
            isAdmin
              ? `<div class="btn-row" style="margin-top:8px">
                   <button class="btn btn-secondary" style="width:auto; padding:6px 14px;" data-edit-event="${e.id}">Edit</button>
                   <button class="btn btn-secondary" style="width:auto; padding:6px 14px;" data-delete-event="${e.id}">Delete</button>
                 </div>
                 <div class="edit-slot" data-edit-slot-for="${e.id}"></div>`
              : ""
          }
        </div>`
            )
            .join("")
        : `<p>Nothing scheduled this day.</p>`
    }
  `;

  if (!isAdmin) return;

  panel.querySelectorAll("[data-edit-event]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const event = events.find((e) => e.id === Number(btn.dataset.editEvent));
      renderEventEditForm(panel.querySelector(`[data-edit-slot-for="${event.id}"]`), event, refresh);
    });
  });
  panel.querySelectorAll("[data-delete-event]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this event? This can't be undone.")) return;
      btn.disabled = true;
      await api.delete(`/api/calendar/${btn.dataset.deleteEvent}`);
      refresh();
    });
  });
}

function renderEventEditForm(slot, event, refresh) {
  slot.innerHTML = `
    <form class="edit-event-form" style="margin-top:12px">
      <div class="field">
        <label>Title</label>
        <input type="text" name="title" value="${escapeHtml(event.title)}" required />
      </div>
      <div class="field">
        <label>Description</label>
        <textarea name="description">${escapeHtml(event.description)}</textarea>
      </div>
      <div class="field">
        <label>Date</label>
        <input type="date" name="date" value="${event.date}" required />
      </div>
      <label class="field" style="display:flex; gap:8px; align-items:center;">
        <input type="checkbox" name="is_blockout" ${event.is_blockout ? "checked" : ""} style="width:auto" />
        Block-out date (other CCAs shouldn't hold events on it)
      </label>
      <div id="edit-event-error"></div>
      <button type="submit" class="btn">Save Changes</button>
    </form>
  `;

  slot.querySelector(".edit-event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = slot.querySelector("#edit-event-error");
    try {
      await api.patch(`/api/calendar/${event.id}`, {
        title: e.target.title.value.trim(),
        description: e.target.description.value.trim() || null,
        event_date: e.target.date.value,
        is_blockout: e.target.is_blockout.checked,
      });
      refresh();
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}

function renderEventForm(panel, user, committees, selectedDate, onSaved) {
  const isAdmin = user.role === "admin";
  panel.innerHTML = `
    <form id="event-form" class="card">
      <h3>New Event</h3>
      <div class="field">
        <label for="ev-title">Title</label>
        <input type="text" id="ev-title" required />
      </div>
      <div class="field">
        <label for="ev-description">Description</label>
        <textarea id="ev-description"></textarea>
      </div>
      <div class="field">
        <label for="ev-date">Date</label>
        <input type="date" id="ev-date" value="${selectedDate || ""}" required />
      </div>
      ${
        isAdmin
          ? `<div class="field">
               <label for="ev-committee">Committee</label>
               <select id="ev-committee" required>
                 ${committees.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}
               </select>
             </div>`
          : ""
      }
      ${
        isAdmin
          ? `<label class="field" style="display:flex; gap:8px; align-items:center;">
               <input type="checkbox" id="ev-blockout" style="width:auto" />
               Block-out date (other CCAs shouldn't hold events on it)
             </label>`
          : ""
      }
      <div id="event-error"></div>
      <button type="submit" class="btn">Add Event</button>
    </form>
  `;

  panel.querySelector("#event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = panel.querySelector("#event-error");
    try {
      await api.post("/api/calendar", {
        title: panel.querySelector("#ev-title").value.trim(),
        description: panel.querySelector("#ev-description").value.trim() || null,
        event_date: panel.querySelector("#ev-date").value,
        committee_id: isAdmin ? Number(panel.querySelector("#ev-committee").value) : null,
        is_blockout: isAdmin ? panel.querySelector("#ev-blockout").checked : false,
      });
      onSaved();
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
