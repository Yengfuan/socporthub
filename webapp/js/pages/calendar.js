import { api } from "../api.js";

const DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
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

  const [committees, events, proposals, feed] = await Promise.all([
    api.get("/api/committees"),
    fetchEvents(year, month, committeeId),
    api.get("/api/proposals").catch(() => []),
    api.get("/api/calendar/feed-url").catch(() => null),
  ]);

  const { start, end, first, last } = gridRange(year, month);
  const eventsByDate = groupByDate(events, (e) => e.date);
  // Only show a proposal's date on the calendar once it's confirmed enough to matter —
  // needs_action/in_review are still "not yet decided", so they'd be noise here.
  const proposalDatesByDate = groupByDate(
    proposals.filter((p) => p.event_date && (p.status === "submitted" || p.status === "finished")),
    (p) => p.event_date
  );

  const monthLabel = first.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });

  const cells = [];
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    const iso = toISODate(d);
    const inMonth = d >= first && d <= last;
    const isToday = iso === toISODate(today);
    const dayEvents = eventsByDate.get(iso) || [];
    const dayProposals = proposalDatesByDate.get(iso) || [];

    cells.push(`
      <div class="cal-cell ${inMonth ? "" : "cal-cell-outside"} ${isToday ? "cal-cell-today" : ""} ${
      selectedDate === iso ? "cal-cell-selected" : ""
    }" data-date="${iso}">
        <div class="cal-daynum">${d.getUTCDate()}</div>
        <div class="cal-dots">
          ${dayEvents
            .slice(0, 3)
            .map((e) => `<span class="cal-dot" style="background:${e.committee_color || "var(--text-muted)"}"></span>`)
            .join("")}
          ${dayProposals.length ? `<span class="cal-dot cal-dot-proposal"></span>` : ""}
        </div>
      </div>
    `);
  }

  root.innerHTML = `
    <h1>Calendar</h1>
    ${
      feed
        ? `<p style="margin-top:-8px">
             <a href="#" id="cal-subscribe">Subscribe from your phone's calendar app</a>
           </p>`
        : ""
    }

    <div class="chip-row">
      <div class="chip ${!committeeId ? "active" : ""}" data-committee="">All</div>
      ${committees
        .map(
          (c) =>
            `<div class="chip ${committeeId == c.id ? "active" : ""}" data-committee="${c.id}">${escapeHtml(c.name)}</div>`
        )
        .join("")}
    </div>

    <div class="page-header">
      <span class="back" id="cal-prev">&larr; Prev</span>
      <h2>${monthLabel}</h2>
      <span class="back" id="cal-next">Next &rarr;</span>
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
  root.querySelector("#cal-subscribe")?.addEventListener("click", (e) => {
    e.preventDefault();
    renderSubscribePanel(root.querySelector("#cal-day-panel"), feed.url);
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
      proposalDatesByDate.get(selectedDate) || [],
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
    <div class="card">
      <h3>Subscribe from your calendar app</h3>
      <p>Add this URL as a subscribed calendar in Google Calendar, Apple Calendar, or Outlook.
      New events show up automatically, though it may take a few hours to refresh.</p>
      <input type="text" readonly value="${url}" style="width:100%; padding:8px; border:1px solid var(--border); border-radius:8px; font-size:12px; margin-bottom:8px;" onclick="this.select()" />
      <button class="btn btn-secondary" id="cal-copy-url">Copy Link</button>
    </div>
  `;
  panel.querySelector("#cal-copy-url").addEventListener("click", async (e) => {
    try {
      await navigator.clipboard.writeText(url);
      e.target.textContent = "Copied!";
      setTimeout(() => (e.target.textContent = "Copy Link"), 1500);
    } catch {
      /* clipboard API unavailable; the input above is selectable as a fallback */
    }
  });
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

function renderDayPanel(panel, dateStr, events, proposals, user, refresh) {
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
            <div class="title">${escapeHtml(e.title)}</div>
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
        : ""
    }
    ${
      proposals.length
        ? proposals
            .map(
              (p) => `
        <a class="card proposal-card" data-nav="proposal/${p.id}">
          <div class="title">${escapeHtml(p.title)}</div>
          <div class="meta"><span>Proposal event date</span></div>
        </a>`
            )
            .join("")
        : ""
    }
    ${!events.length && !proposals.length ? `<p>Nothing scheduled this day.</p>` : ""}
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
      });
      onSaved();
    } catch (err) {
      errorEl.innerHTML = `<div class="error-banner">${err.message}</div>`;
    }
  });
}
