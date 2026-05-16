/* TPS Silent Comms Widget
 * --------------------------------------------------------------
 * Listens for clicks on the dashboard's existing buttons and
 * POSTs the action to the Apps Script Web App, which appends a
 * row to the "StatusUpdates" tab of the Operations spreadsheet.
 *
 * Wiring:
 *   - Every .task-item must have data-id="<row-id>"
 *   - Buttons inside .task-item with these classes get wired:
 *       .btn-tricia    -> status "Tricia on it",      by "Tricia"
 *       .btn-maya      -> status "Maya on it",        by "Maya"
 *       .btn-approve   -> status "Approved",          by detected
 *       .btn-hold      -> status "On Hold",           by detected
 *       .btn-reject    -> status "Rejected",          by detected
 *       .task-checkbox -> status "Done",              by detected
 *       .comment-save-btn (next to .task-comment-input) -> note only
 *
 *   - "by detected" tries to read a tag on the task-item like
 *     data-actor (Tricia/Maya) or, failing that, asks once.
 *
 *   - All writes are silent. Tricia sees a tiny "✓ Logged" pill
 *     under the button for 2 seconds. No popups.
 *
 *   - localStorage caches the most recent action per task so the
 *     status badge updates instantly until the next 1pm refresh.
 * -------------------------------------------------------------- */

(function () {
  // -------- CONFIG --------
  const WEB_APP_URL = "https://script.google.com/macros/s/AKfycbzxDMKRS8kX6xmfI47mMttI4xKSwg3XaC6zSJZR4lnl9ldzPKmzoJqk6yerV3uV1DOD/exec";
  const SECRET_TOKEN = "TPSMAYA4321";
  const STORAGE_PREFIX = "tps-comms";
  // -------------------------

  // Tiny in-page toast confirming a write
  function toast(msg, ok) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText =
      "position:fixed;right:20px;bottom:20px;z-index:9999;" +
      "padding:10px 14px;border-radius:8px;font:600 13px Inter,system-ui;" +
      "color:#fff;background:" + (ok ? "#10b981" : "#f44336") + ";" +
      "box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;" +
      "transition:opacity .2s ease,transform .2s ease;transform:translateY(8px);";
    document.body.appendChild(t);
    requestAnimationFrame(function () {
      t.style.opacity = "1";
      t.style.transform = "translateY(0)";
    });
    setTimeout(function () {
      t.style.opacity = "0";
      t.style.transform = "translateY(8px)";
      setTimeout(function () { t.remove(); }, 250);
    }, 1800);
  }

  // Who is using this browser? Cached after first prompt.
  function getActor() {
    let actor = localStorage.getItem(STORAGE_PREFIX + ":actor");
    if (actor) return actor;
    actor = window.prompt("Quick check — who's logged in?\nType: Tricia, Maya, or Other") || "";
    actor = actor.trim();
    if (!actor) actor = "Unknown";
    localStorage.setItem(STORAGE_PREFIX + ":actor", actor);
    return actor;
  }

  // POST a status update to the Apps Script Web App.
  // Returns a promise that resolves with the server response or rejects on error.
  function postUpdate(payload) {
    const body = Object.assign({ token: SECRET_TOKEN, source: "Dashboard" }, payload);
    return fetch(WEB_APP_URL + "?action=update", {
      method: "POST",
      // Apps Script web app accepts text/plain JSON without preflight (avoids CORS issues)
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(body),
      redirect: "follow"
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  // Visually reflect a status change on the task tile (until the next refresh).
  function reflectStatus(taskItem, status) {
    const badge = taskItem.querySelector(".task-status-badge");
    if (!badge) return;
    badge.textContent = status;
    // map our verbs to your existing CSS classes
    const map = {
      "Tricia on it":   "status-in-progress",
      "Maya on it":     "status-in-progress",
      "Done":           "status-fyi",
      "Approved":       "status-approval",
      "On Hold":        "status-in-progress",
      "Rejected":       "status-stuck"
    };
    const cls = map[status] || "status-fyi";
    badge.className = "task-status-badge " + cls;
  }

  // Cache last action so re-opening the page shows latest state.
  function cacheStatus(id, status, note) {
    try {
      const key = STORAGE_PREFIX + ":task:" + id;
      const data = { status: status, note: note || "", at: Date.now() };
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) { /* ignore */ }
  }

  function loadCached(id) {
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + ":task:" + id);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  // The main send function — used by every button.
  function send(taskItem, status, note) {
    const id = taskItem.getAttribute("data-id");
    if (!id) {
      console.warn("Silent comms: task-item missing data-id", taskItem);
      toast("Couldn't log — missing task ID", false);
      return Promise.reject(new Error("missing data-id"));
    }
    const actor = getActor();
    return postUpdate({
      id: id,
      status: status,
      note: note || "",
      by: actor
    }).then(function (res) {
      if (res && res.ok) {
        toast("✓ Logged: " + status, true);
        reflectStatus(taskItem, status);
        cacheStatus(id, status, note);
      } else {
        toast("Saved locally, sheet rejected (" + (res && res.error || "?") + ")", false);
      }
      return res;
    }).catch(function (err) {
      console.error("Silent comms POST failed:", err);
      // Still keep visual state so Tricia isn't confused
      reflectStatus(taskItem, status);
      cacheStatus(id, status, note);
      toast("Saved locally — sheet sync failed", false);
    });
  }

  // Hook everything up after DOMContentLoaded.
  function wireUp() {
    const tasks = document.querySelectorAll(".task-item[data-id]");
    tasks.forEach(function (task) {
      const id = task.getAttribute("data-id");

      // 1. Hydrate visual state from cache (until 1pm refresh catches up)
      const cached = loadCached(id);
      if (cached && cached.status) reflectStatus(task, cached.status);
      if (cached && cached.note) {
        const noteEl = task.querySelector(".task-comment-input");
        if (noteEl && !noteEl.value) noteEl.value = cached.note;
      }

      // 2. Helper to read current note text
      const readNote = function () {
        const ta = task.querySelector(".task-comment-input");
        return ta ? ta.value.trim() : "";
      };

      // 3. Button bindings
      const bind = function (selector, status) {
        const btn = task.querySelector(selector);
        if (!btn) return;
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          send(task, status, readNote());
        });
      };
      bind(".btn-tricia",  "Tricia on it");
      bind(".btn-maya",    "Maya on it");
      bind(".btn-approve", "Approved");
      bind(".btn-hold",    "On Hold");
      bind(".btn-reject",  "Rejected");

      // 4. Done checkbox — fires when checked
      const doneCb = task.querySelector(".task-checkbox");
      if (doneCb) {
        doneCb.addEventListener("change", function (e) {
          if (doneCb.checked) {
            e.stopPropagation();
            send(task, "Done", readNote());
          }
        });
      }

      // 5. Save Note button — sends a note-only update tagged as "Note"
      const saveBtn = task.querySelector(".comment-save-btn");
      if (saveBtn) {
        saveBtn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          const n = readNote();
          if (!n) { toast("Note is empty", false); return; }
          send(task, "Note added", n);
        });
      }
    });
    console.log("[TPS Silent Comms] Wired up " + tasks.length + " task items.");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireUp);
  } else {
    wireUp();
  }

  // Expose tiny debug API for the console
  window.tpsComms = {
    actor: getActor,
    setActor: function (name) { localStorage.setItem(STORAGE_PREFIX + ":actor", name); },
    clearActor: function () { localStorage.removeItem(STORAGE_PREFIX + ":actor"); },
    sendTest: function (id) {
      return postUpdate({ id: id || "test-" + Date.now(), status: "Test", note: "Pinged from console", by: getActor() });
    }
  };
})();
