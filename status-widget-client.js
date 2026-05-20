/* TPS Dashboard Widget v2
 * --------------------------------------------------------------
 * Handles: silent status updates, actor picker, signed-in pill,
 *          and the "+ Add a task" wizard.
 * All UI injected by JS — no other dashboard files need to change.
 * -------------------------------------------------------------- */

(function () {
  // ============================== CONFIG ==============================
  const WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxbNL6TKDf1z2SS9HAczKvYN1oSnY1WOEuMPa4Qv9VY76OuewyeBLvADNQiJI4wtppP/exec";
  const SECRET_TOKEN = "TPSMAYA4321";
  const STORAGE_PREFIX = "tps-comms";
  const KNOWN_ACTORS = ["Maya", "Tricia", "Craig"];

  const PROPERTIES = [
    "17 Mayflower","17 Mayflower, Unit Lower","17 Mayflower, Unit 1",
    "Britannia","Britannia, Unit 1","Britannia, Unit 2",
    "Deschene","Deschene, Unit 1",
    "Dufferin","Dufferin, Unit 1 Main","Dufferin, Unit 2 Upper",
    "Fairleigh","Fairleigh, Unit 1","Fairleigh, Unit 2","Fairleigh, Unit 3",
    "Ferndale","Ferndale, Unit 1","Ferndale, Unit 2",
    "Grandfield","Grandfield, Unit 1","Grandfield, Unit 2","Grandfield, Unit 3",
    "Grantham","Grantham, Unit 1","Grantham, Unit 2",
    "Mohawk","Mohawk, Unit 1","Mohawk, Unit 2","Mohawk, Unit 3","Mohawk, Unit 4","Mohawk, Unit 5","Mohawk, Unit 6",
    "Myrtle Ave","Myrtle Ave, Unit C3","Myrtle Ave, Unit 101","Myrtle Ave, Unit 201",
    "Thayer","Thayer, Unit 1","Thayer, Unit 2","Thayer, Unit 3",
    "Upper Sherman","Upper Sherman, Unit 1","Upper Sherman, Unit 2",
    "Upper Wellington","Upper Wellington, Unit 1","Upper Wellington, Unit 2","Upper Wellington, Unit 3",
    "Wellington South","Wellington South, Unit 1","Wellington South, Unit 2","Wellington South, Unit 3","Wellington South, Unit 4","Wellington South, Unit 5",
    "West 4th","West 4th, Unit 1","West 4th, Unit 2","West 4th, Unit 3BR"
  ];
  const CATEGORIES = ["Operations & Admin","Maintenance & Repairs","Financials & Accounting","Leasing & Marketing"];
  const PRIORITIES = [
    { emoji: "🔴", label: "High",   value: "High"   },
    { emoji: "🟡", label: "Medium", value: "Medium" },
    { emoji: "🟢", label: "Low",    value: "Low"    }
  ];

  // ============================== STYLES ==============================
  function injectStyles() {
    if (document.getElementById("tps-widget-styles")) return;
    const css = `
      .tps-add-task-btn {
        display: inline-flex; align-items: center; justify-content: center;
        border-radius: 1rem;
        background: linear-gradient(173deg, #23272f 0%, #14161a 100%);
        box-shadow: 8px 8px 16px #0e1013, -8px -8px 24px rgba(56,62,75,0.5);
        padding: 0.55rem 1.1rem;
        color: #fff; border: 1px solid transparent;
        cursor: pointer; transition: all 0.2s ease-in-out;
        font-family: inherit; font-size: 14px; font-weight: 500;
        letter-spacing: 0.2px; white-space: nowrap; line-height: 1;
      }
      .tps-add-task-btn:hover {
        border-color: #ffd43b;
        box-shadow: 0 0 24px rgba(255,212,59,0.45), 0 0 24px rgba(255,102,0,0.35),
                    inset 0 0 10px rgba(255,102,0,0.25), 8px 8px 16px #0e1013;
      }
      .tps-add-task-btn:focus { outline: none; border-color: #ffd43b;
        box-shadow: 0 0 30px rgba(255,212,59,0.55), 0 0 30px rgba(255,102,0,0.45),
                    inset 0 0 12px rgba(255,102,0,0.35), 8px 8px 16px #0e1013; }
      .tps-add-task-btn:active { transform: translateY(1px); }
      @media (max-width: 500px) { .tps-add-task-btn { padding: 0.5rem 0.9rem; font-size: 13px; } }

      .tps-signed-pill {
        position: fixed; right: 16px; bottom: 16px; z-index: 9998;
        background: rgba(35,39,47,0.92); color: #fff;
        font: 500 12px/1.2 Inter, system-ui, sans-serif;
        padding: 8px 14px; border-radius: 999px; cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        display: inline-flex; align-items: center; gap: 8px;
        transition: background 0.15s ease;
      }
      .tps-signed-pill:hover { background: rgba(35,39,47,1); }
      .tps-signed-pill .tps-pill-switch { font-size: 11px; opacity: 0.6; }

      .tps-modal-overlay {
        position: fixed; inset: 0; z-index: 10000;
        background: rgba(15,17,21,0.55);
        display: flex; align-items: center; justify-content: center;
        padding: 16px; backdrop-filter: blur(4px);
        animation: tps-fade-in 0.15s ease;
      }
      @keyframes tps-fade-in { from { opacity: 0; } to { opacity: 1; } }
      .tps-modal {
        background: #fff; color: #1f2937;
        border-radius: 16px; max-width: 480px; width: 100%;
        padding: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        font-family: Inter, system-ui, sans-serif;
        max-height: 90vh; overflow-y: auto;
      }
      body.dark-mode .tps-modal { background: #1a1d23; color: #f1f1f1; }
      .tps-modal h2 { font: 600 18px/1.3 inherit; margin: 0 0 6px; }
      .tps-modal .tps-modal-sub { font-size: 13px; color: #6b7280; margin: 0 0 18px; }
      body.dark-mode .tps-modal .tps-modal-sub { color: #9ca3af; }

      .tps-actor-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-bottom: 12px; }
      .tps-actor-btn {
        padding: 14px 8px; border-radius: 10px; border: 1.5px solid #e5e5e0;
        background: #fff; color: #1f2937; font: 600 15px/1.2 inherit;
        cursor: pointer; transition: all 0.15s ease;
      }
      .tps-actor-btn:hover { border-color: #1D9E75; background: #EAF3DE; }
      body.dark-mode .tps-actor-btn { background: #23272f; color: #f1f1f1; border-color: #383e4b; }
      body.dark-mode .tps-actor-btn:hover { border-color: #1D9E75; background: #1f2a23; }
      .tps-actor-other {
        display: block; margin-top: 4px; padding: 8px; text-align: center;
        background: transparent; border: none; color: #6b7280;
        font: 400 13px/1.2 inherit; cursor: pointer; width: 100%;
      }
      .tps-actor-other:hover { color: #1D9E75; }

      .tps-wiz-progress { font-size: 12px; color: #6b7280; margin: 0 0 8px; letter-spacing: 0.3px; }
      .tps-wiz-question { font: 600 17px/1.3 inherit; margin: 0 0 14px; color: inherit; }
      .tps-wiz-field { width: 100%; padding: 10px 12px; border: 1.5px solid #e5e5e0; border-radius: 8px;
        font: 400 15px/1.4 inherit; color: inherit; background: #fff; box-sizing: border-box; }
      .tps-wiz-field:focus { outline: none; border-color: #1D9E75; }
      body.dark-mode .tps-wiz-field { background: #23272f; color: #f1f1f1; border-color: #383e4b; }
      textarea.tps-wiz-field { min-height: 80px; resize: vertical; }
      .tps-wiz-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
      .tps-wiz-opt {
        text-align: left; padding: 12px 14px; border: 1.5px solid #e5e5e0; border-radius: 10px;
        background: #fff; color: inherit; font: 500 15px/1.3 inherit; cursor: pointer;
        transition: all 0.15s ease;
      }
      .tps-wiz-opt:hover { border-color: #1D9E75; background: #EAF3DE; }
      .tps-wiz-opt.selected { border-color: #1D9E75; background: #d4ebbf; }
      body.dark-mode .tps-wiz-opt { background: #23272f; color: #f1f1f1; border-color: #383e4b; }
      body.dark-mode .tps-wiz-opt:hover, body.dark-mode .tps-wiz-opt.selected { background: #1f2a23; border-color: #1D9E75; }

      .tps-wiz-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 18px; }
      .tps-wiz-btn { padding: 10px 18px; border-radius: 8px; border: none; cursor: pointer; font: 500 14px/1.2 inherit; transition: all 0.15s ease; }
      .tps-wiz-btn.primary { background: #1D9E75; color: #fff; }
      .tps-wiz-btn.primary:hover { background: #168661; }
      .tps-wiz-btn.primary:disabled { background: #cbd5d0; cursor: not-allowed; }
      .tps-wiz-btn.secondary { background: transparent; color: #6b7280; }
      .tps-wiz-btn.secondary:hover { color: #1f2937; }
      body.dark-mode .tps-wiz-btn.secondary:hover { color: #f1f1f1; }

      .tps-typeahead-wrap { position: relative; }
      .tps-typeahead-list { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 10;
        background: #fff; border: 1px solid #e5e5e0; border-radius: 8px;
        max-height: 240px; overflow-y: auto; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
      body.dark-mode .tps-typeahead-list { background: #23272f; border-color: #383e4b; }
      .tps-typeahead-item { padding: 10px 12px; font-size: 14px; cursor: pointer; }
      .tps-typeahead-item:hover, .tps-typeahead-item.active { background: #EAF3DE; }
      body.dark-mode .tps-typeahead-item:hover, body.dark-mode .tps-typeahead-item.active { background: #1f2a23; }
    `;
    const style = document.createElement("style");
    style.id = "tps-widget-styles";
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ============================== TOAST ==============================
  function toast(msg, ok) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText =
      "position:fixed;right:20px;bottom:64px;z-index:9999;" +
      "padding:10px 14px;border-radius:8px;font:600 13px Inter,system-ui;" +
      "color:#fff;background:" + (ok ? "#10b981" : "#f44336") + ";" +
      "box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;" +
      "transition:opacity .2s ease,transform .2s ease;transform:translateY(8px);";
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.style.opacity = "1"; t.style.transform = "translateY(0)"; });
    setTimeout(function () {
      t.style.opacity = "0"; t.style.transform = "translateY(8px)";
      setTimeout(function () { t.remove(); }, 250);
    }, 1800);
  }

  // ============================== ACTOR MANAGEMENT ==============================
  function isValidActor(name) {
    if (!name) return false;
    name = String(name).trim();
    if (KNOWN_ACTORS.includes(name)) return true;
    if (name.length > 0 && name.length < 20 && !/[\s,.;:!?\n]/.test(name)) return true;
    return false;
  }
  function getActor() {
    const raw = localStorage.getItem(STORAGE_PREFIX + ":actor");
    if (isValidActor(raw)) return raw.trim();
    return null;
  }
  function setActor(name) {
    localStorage.setItem(STORAGE_PREFIX + ":actor", name);
    updateSignedInPill();
  }
  function clearActor() {
    localStorage.removeItem(STORAGE_PREFIX + ":actor");
    updateSignedInPill();
  }

  // ============================== MODAL CORE ==============================
  function openModal(content) {
    closeModal();
    const overlay = document.createElement("div");
    overlay.className = "tps-modal-overlay";
    overlay.id = "tps-modal-overlay";
    const modal = document.createElement("div");
    modal.className = "tps-modal";
    if (typeof content === "string") modal.innerHTML = content;
    else modal.appendChild(content);
    overlay.appendChild(modal);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeModal(); });
    document.body.appendChild(overlay);
    return modal;
  }
  function closeModal() {
    const ex = document.getElementById("tps-modal-overlay");
    if (ex) ex.remove();
  }

  // ============================== ACTOR PICKER ==============================
  function showActorPicker() {
    return new Promise(function (resolve) {
      const wrapper = document.createElement("div");
      wrapper.innerHTML =
        '<h2>Who\'s making this note?</h2>' +
        '<p class="tps-modal-sub">Just tap your name. We\'ll remember on this device.</p>' +
        '<div class="tps-actor-row">' +
          '<button class="tps-actor-btn" data-actor="Maya">I\'m Maya</button>' +
          '<button class="tps-actor-btn" data-actor="Tricia">I\'m Tricia</button>' +
          '<button class="tps-actor-btn" data-actor="Craig">I\'m Craig</button>' +
        '</div>' +
        '<button class="tps-actor-other" id="tps-other-btn">Someone else…</button>';
      const modal = openModal(wrapper);
      modal.querySelectorAll(".tps-actor-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          const name = btn.getAttribute("data-actor");
          setActor(name); closeModal(); resolve(name);
        });
      });
      modal.querySelector("#tps-other-btn").addEventListener("click", function () {
        const name = window.prompt("Your first name (one word only):");
        if (name && isValidActor(name)) {
          setActor(name.trim()); closeModal(); resolve(name.trim());
        } else if (name) {
          alert("Please use one word, no spaces (e.g. Maya).");
        }
      });
    });
  }

  function ensureActor() {
    return new Promise(function (resolve) {
      const cur = getActor();
      if (cur) return resolve(cur);
      showActorPicker().then(resolve);
    });
  }

  // ============================== SIGNED-IN PILL ==============================
  function createSignedInPill() {
    if (document.getElementById("tps-signed-pill")) return;
    const pill = document.createElement("div");
    pill.id = "tps-signed-pill";
    pill.className = "tps-signed-pill";
    pill.addEventListener("click", function () { showActorPicker(); });
    document.body.appendChild(pill);
    updateSignedInPill();
  }
  function updateSignedInPill() {
    const pill = document.getElementById("tps-signed-pill");
    if (!pill) return;
    const actor = getActor();
    if (actor) {
      pill.innerHTML = '<span>👤 ' + actor + '</span><span class="tps-pill-switch">switch</span>';
    } else {
      pill.innerHTML = '<span>👤 Sign in</span>';
    }
  }

  // ============================== ADD TASK BUTTON ==============================
  function createAddTaskButton() {
    const header = document.querySelector(".page-header");
    if (!header || header.querySelector(".tps-add-task-btn")) return;
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    header.style.flexWrap = "wrap";
    header.style.gap = "12px";
    const left = document.createElement("div");
    while (header.firstChild) left.appendChild(header.firstChild);
    header.appendChild(left);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tps-add-task-btn";
    btn.innerHTML = '<span style="margin-right:6px;font-size:16px;line-height:1;">+</span><span>Add a task</span>';
    btn.addEventListener("click", openAddTaskWizard);
    header.appendChild(btn);
  }

  // ============================== ADD TASK WIZARD ==============================
  function openAddTaskWizard() {
    ensureActor().then(function (actor) {
      const state = { step: 0, property: "", task: "", notes: "", category: "", priority: "", assignedTo: actor };
      const steps = [renderStepProperty, renderStepTask, renderStepNotes, renderStepCategory, renderStepPriority, renderStepAssign, renderStepReview];
      const wrapper = document.createElement("div");
      openModal(wrapper);
      function go(delta) { state.step = Math.max(0, Math.min(steps.length - 1, state.step + delta)); render(); }
      function setAndNext(key, val) { if (key) state[key] = val; if (state.step < steps.length - 1) go(1); else submit(); }
      function render() {
        wrapper.innerHTML = "";
        const prog = document.createElement("div");
        prog.className = "tps-wiz-progress";
        prog.textContent = "Step " + (state.step + 1) + " of " + steps.length;
        wrapper.appendChild(prog);
        steps[state.step](wrapper, state, setAndNext, go);
      }
      function submit() {
        wrapper.innerHTML = '<h2>Adding task…</h2><p class="tps-modal-sub">One moment.</p>';
        postAddTask({ property: state.property, task: state.task, notes: state.notes, category: state.category, priority: state.priority, assignedTo: state.assignedTo, by: actor })
          .then(function (res) {
            if (res && res.ok) {
              wrapper.innerHTML = '<h2>✓ Task added</h2><p class="tps-modal-sub">It\'s now in the Operations Log. It will appear on the dashboard at the next 1pm refresh.</p><div class="tps-wiz-actions"><span></span><button class="tps-wiz-btn primary" id="tps-done">Done</button></div>';
              wrapper.querySelector("#tps-done").addEventListener("click", closeModal);
              cacheNewTask(state);
            } else {
              wrapper.innerHTML = '<h2>Couldn\'t save</h2><p class="tps-modal-sub">' + ((res && res.error) || "Network issue") + '</p><div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">Try again</button><button class="tps-wiz-btn primary" id="tps-close">Close</button></div>';
              wrapper.querySelector("#tps-back").addEventListener("click", function () { state.step = steps.length - 1; render(); });
              wrapper.querySelector("#tps-close").addEventListener("click", closeModal);
            }
          }).catch(function () {
            wrapper.innerHTML = '<h2>Network problem</h2><p class="tps-modal-sub">Couldn\'t reach the spreadsheet. Try again in a moment.</p><div class="tps-wiz-actions"><span></span><button class="tps-wiz-btn primary" id="tps-close">Close</button></div>';
            wrapper.querySelector("#tps-close").addEventListener("click", closeModal);
          });
      }
      render();
    });
  }

  function renderStepProperty(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend",
      '<h2 class="tps-wiz-question">Which property?</h2>' +
      '<div class="tps-typeahead-wrap"><input type="text" class="tps-wiz-field" id="tps-prop-input" placeholder="Type to search…" autocomplete="off" />' +
      '<div class="tps-typeahead-list" id="tps-prop-list" style="display:none;"></div></div>' +
      '<div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-cancel">Cancel</button><button class="tps-wiz-btn primary" id="tps-next" disabled>Next →</button></div>');
    const input = wrap.querySelector("#tps-prop-input");
    const list = wrap.querySelector("#tps-prop-list");
    const next = wrap.querySelector("#tps-next");
    if (state.property) { input.value = state.property; next.disabled = false; }
    wrap.querySelector("#tps-cancel").addEventListener("click", closeModal);
    next.addEventListener("click", function () { state.property = input.value; setAndNext(null, null); });
    function show(items) {
      list.innerHTML = "";
      items.slice(0, 30).forEach(function (p) {
        const it = document.createElement("div");
        it.className = "tps-typeahead-item";
        it.textContent = p;
        it.addEventListener("click", function () { input.value = p; state.property = p; next.disabled = false; list.style.display = "none"; });
        list.appendChild(it);
      });
      list.style.display = items.length ? "block" : "none";
    }
    input.addEventListener("focus", function () { show(PROPERTIES); });
    input.addEventListener("input", function () {
      const q = input.value.trim().toLowerCase();
      const matched = !q ? PROPERTIES : PROPERTIES.filter(function (p) { return p.toLowerCase().indexOf(q) > -1; });
      show(matched);
      next.disabled = !PROPERTIES.includes(input.value.trim());
    });
    input.addEventListener("blur", function () { setTimeout(function () { list.style.display = "none"; }, 150); });
    setTimeout(function () { input.focus(); }, 50);
  }
  function renderStepTask(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend",
      '<h2 class="tps-wiz-question">What\'s the task?</h2>' +
      '<input type="text" class="tps-wiz-field" id="tps-task-input" placeholder="e.g. Replace bathroom faucet" autocomplete="off" />' +
      '<div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><button class="tps-wiz-btn primary" id="tps-next" disabled>Next →</button></div>');
    const input = wrap.querySelector("#tps-task-input");
    const next = wrap.querySelector("#tps-next");
    if (state.task) { input.value = state.task; next.disabled = false; }
    input.addEventListener("input", function () { next.disabled = !input.value.trim(); });
    input.addEventListener("keydown", function (e) { if (e.key === "Enter" && input.value.trim()) next.click(); });
    next.addEventListener("click", function () { state.task = input.value.trim(); setAndNext(null, null); });
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
    setTimeout(function () { input.focus(); }, 50);
  }
  function renderStepNotes(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend",
      '<h2 class="tps-wiz-question">Any notes? <span style="font-weight:400;color:#9ca3af;font-size:14px;">(optional)</span></h2>' +
      '<textarea class="tps-wiz-field" id="tps-notes-input" placeholder="Add detail, vendor name, deadline…"></textarea>' +
      '<div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><button class="tps-wiz-btn primary" id="tps-next">Next →</button></div>');
    const ta = wrap.querySelector("#tps-notes-input");
    if (state.notes) ta.value = state.notes;
    wrap.querySelector("#tps-next").addEventListener("click", function () { state.notes = ta.value.trim(); setAndNext(null, null); });
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
    setTimeout(function () { ta.focus(); }, 50);
  }
  function renderStepCategory(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend", '<h2 class="tps-wiz-question">Category?</h2><div class="tps-wiz-options" id="tps-cat-opts"></div><div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><span></span></div>');
    const opts = wrap.querySelector("#tps-cat-opts");
    CATEGORIES.forEach(function (cat) {
      const b = document.createElement("button");
      b.className = "tps-wiz-opt" + (state.category === cat ? " selected" : "");
      b.textContent = cat;
      b.addEventListener("click", function () { state.category = cat; setAndNext(null, null); });
      opts.appendChild(b);
    });
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
  }
  function renderStepPriority(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend", '<h2 class="tps-wiz-question">Priority?</h2><div class="tps-wiz-options" id="tps-pri-opts"></div><div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><span></span></div>');
    const opts = wrap.querySelector("#tps-pri-opts");
    PRIORITIES.forEach(function (p) {
      const b = document.createElement("button");
      b.className = "tps-wiz-opt" + (state.priority === p.value ? " selected" : "");
      b.innerHTML = '<span style="margin-right:8px;">' + p.emoji + '</span>' + p.label;
      b.addEventListener("click", function () { state.priority = p.value; setAndNext(null, null); });
      opts.appendChild(b);
    });
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
  }
  function renderStepAssign(wrap, state, setAndNext, go) {
    wrap.insertAdjacentHTML("beforeend", '<h2 class="tps-wiz-question">Assign to?</h2><div class="tps-wiz-options" id="tps-asg-opts"></div><div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><span></span></div>');
    const opts = wrap.querySelector("#tps-asg-opts");
    ["Maya", "Tricia", "Craig", "Unassigned"].forEach(function (name) {
      const b = document.createElement("button");
      b.className = "tps-wiz-opt" + (state.assignedTo === name ? " selected" : "");
      b.textContent = name;
      b.addEventListener("click", function () { state.assignedTo = name; setAndNext(null, null); });
      opts.appendChild(b);
    });
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
  }
  function renderStepReview(wrap, state, setAndNext, go) {
    const rows = [["Property", state.property],["Task", state.task],["Notes", state.notes || "—"],["Category", state.category],["Priority", state.priority],["Assigned to", state.assignedTo]];
    let html = '<h2 class="tps-wiz-question">Review &amp; add</h2><div style="background:rgba(0,0,0,0.04);border-radius:10px;padding:14px;margin-bottom:14px;"><table style="width:100%;font-size:14px;border-collapse:collapse;">';
    rows.forEach(function (r) { html += '<tr><td style="padding:5px 12px 5px 0;color:#6b7280;width:35%;vertical-align:top;">' + r[0] + '</td><td style="padding:5px 0;">' + escapeHtml(r[1] || "—") + '</td></tr>'; });
    html += '</table></div><div class="tps-wiz-actions"><button class="tps-wiz-btn secondary" id="tps-back">← Back</button><button class="tps-wiz-btn primary" id="tps-add">✓ Add task</button></div>';
    wrap.insertAdjacentHTML("beforeend", html);
    wrap.querySelector("#tps-back").addEventListener("click", function () { go(-1); });
    wrap.querySelector("#tps-add").addEventListener("click", function () { setAndNext(null, null); });
  }
  function escapeHtml(s) { return String(s || "").replace(/[&<>"']/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]; }); }

  // ============================== POST HELPERS ==============================
  function postUpdate(payload) {
    const body = Object.assign({ token: SECRET_TOKEN, source: "Dashboard" }, payload);
    return fetch(WEB_APP_URL + "?action=update", { method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(body), redirect: "follow" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  function postAddTask(payload) {
    const body = Object.assign({ token: SECRET_TOKEN, source: "Dashboard" }, payload);
    return fetch(WEB_APP_URL + "?action=addTask", { method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(body), redirect: "follow" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }
  function cacheNewTask(state) {
    try {
      const key = STORAGE_PREFIX + ":new-tasks";
      const list = JSON.parse(localStorage.getItem(key) || "[]");
      list.push({ at: Date.now(), property: state.property, task: state.task, notes: state.notes, category: state.category, priority: state.priority, assignedTo: state.assignedTo });
      const cutoff = Date.now() - 24 * 60 * 60 * 1000;
      const kept = list.filter(function (it) { return it.at > cutoff; });
      localStorage.setItem(key, JSON.stringify(kept));
    } catch (e) {}
  }

  // ============================== STATUS UPDATES (existing buttons) ==============================
  function reflectStatus(taskItem, status) {
    const badge = taskItem.querySelector(".task-status-badge");
    if (!badge) return;
    badge.textContent = status;
    const map = { "Tricia on it": "status-in-progress", "Maya on it": "status-in-progress", "Craig on it": "status-in-progress", "Done": "status-fyi", "Approved": "status-approval", "On Hold": "status-in-progress", "Rejected": "status-stuck" };
    badge.className = "task-status-badge " + (map[status] || "status-fyi");
  }
  function cacheStatus(id, status, note) {
    try { localStorage.setItem(STORAGE_PREFIX + ":task:" + id, JSON.stringify({ status: status, note: note || "", at: Date.now() })); } catch (e) {}
  }
  function loadCached(id) {
    try { const raw = localStorage.getItem(STORAGE_PREFIX + ":task:" + id); return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  }
  function send(taskItem, status, note) {
    const id = taskItem.getAttribute("data-id");
    if (!id) { toast("Couldn't log — missing task ID", false); return Promise.reject(); }
    const property = (taskItem.querySelector(".task-property")?.textContent || "").trim();
    const taskTitle = (taskItem.querySelector(".task-title")?.textContent || "").trim();
    return ensureActor().then(function (actor) {
      return postUpdate({ id: id, property: property, task: taskTitle, status: status, note: note || "", by: actor })
        .then(function (res) {
          if (res && res.ok) { toast("✓ Logged: " + status, true); reflectStatus(taskItem, status); cacheStatus(id, status, note); }
          else { toast("Saved locally — sheet rejected", false); reflectStatus(taskItem, status); cacheStatus(id, status, note); }
          return res;
        }).catch(function () { reflectStatus(taskItem, status); cacheStatus(id, status, note); toast("Saved locally — sheet sync failed", false); });
    });
  }

  // ============================== WIRING ==============================
  function wireTasks() {
    const tasks = document.querySelectorAll(".task-item[data-id]");
    tasks.forEach(function (task) {
      const id = task.getAttribute("data-id");
      const cached = loadCached(id);
      if (cached && cached.status) reflectStatus(task, cached.status);
      if (cached && cached.note) { const n = task.querySelector(".task-comment-input"); if (n && !n.value) n.value = cached.note; }
      const readNote = function () { const ta = task.querySelector(".task-comment-input"); return ta ? ta.value.trim() : ""; };
      const bind = function (sel, status) {
        const btn = task.querySelector(sel);
        if (!btn) return;
        btn.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); send(task, status, readNote()); });
      };
      bind(".btn-tricia", "Tricia on it");
      bind(".btn-maya", "Maya on it");
      bind(".btn-craig", "Craig on it");
      bind(".btn-approve", "Approved");
      bind(".btn-hold", "On Hold");
      bind(".btn-reject", "Rejected");
      const doneCb = task.querySelector(".task-checkbox");
      if (doneCb) doneCb.addEventListener("change", function (e) { if (doneCb.checked) { e.stopPropagation(); send(task, "Done", readNote()); } });
      const saveBtn = task.querySelector(".comment-save-btn");
      if (saveBtn) saveBtn.addEventListener("click", function (e) {
        e.preventDefault(); e.stopPropagation();
        const n = readNote();
        if (!n) { toast("Note is empty", false); return; }
        send(task, "Note added", n);
      });
    });
    console.log("[TPS Widget] Wired " + tasks.length + " task items.");
  }

  // ============================== INIT ==============================
  function init() {
    const stored = localStorage.getItem(STORAGE_PREFIX + ":actor");
    if (stored && !isValidActor(stored)) {
      console.log("[TPS Widget] Clearing invalid stored actor:", stored);
      localStorage.removeItem(STORAGE_PREFIX + ":actor");
    }
    injectStyles();
    createSignedInPill();
    createAddTaskButton();
    wireTasks();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  window.tpsComms = {
    actor: getActor, setActor: setActor, clearActor: clearActor,
    pickActor: showActorPicker, openWizard: openAddTaskWizard,
    sendTest: function (id) { return postUpdate({ id: id || "test-" + Date.now(), status: "Test", note: "Pinged from console", by: getActor() || "Unknown" }); }
  };
})();
