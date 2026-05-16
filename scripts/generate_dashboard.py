#!/usr/bin/env python3
"""
TPS Daily Dashboard Generator
-----------------------------
Reads Google Sheets Operations Log + Archive + StatusUpdates, generates a fresh
index.html every day at 1 PM Eastern via GitHub Actions.

Key features:
  * Each rendered task tile carries data-id="<sheet row id>" so the silent-comms
    widget (status-widget-client.js) can POST updates back to the spreadsheet.
  * Latest entries from the StatusUpdates tab overlay the Operations Log status
    so Tricia's morning actions appear on the 1 PM refresh.
  * No inline onclick handlers — all behavior comes from status-widget-client.js.
"""

import os
import json
import re
from datetime import datetime
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SPREADSHEET_ID = os.environ.get(
    "SPREADSHEET_ID",
    "1G2JYQp-zvGEHEbBIJuniRG3itq0ysNdOGuVsy-WGKg4",  # Maya's live Operations sheet
)
OPS_LOG_TAB = "Operations Log"
ARCHIVE_TAB = "📦 Archive"
STATUS_UPDATES_TAB = "StatusUpdates"

# Paths are relative to the repo root (GitHub Actions checks out to repo root).
TEMPLATE_HTML = "scripts/dashboard-template.html"
INDEX_HTML = "index.html"

CATEGORY_ORDER = [
    "Operations & Admin",
    "Leasing & Marketing",
    "Maintenance & Repairs",
    "Financials & Accounting",
    "Tenant Relations",
]

STATUS_ORDER = ["Stuck", "Maya Needs Help", "New", "In Progress", "FYI Only"]

VALID_STATUSES = {
    "Needs Approval",
    "Maya Needs Help",
    "New",
    "In Progress",
    "Stuck",
    "FYI Only",
}

STATUS_CLASS_MAP = {
    "Needs Approval":   "status-approval",
    "Maya Needs Help":  "status-maya-help",
    "New":              "status-new",
    "In Progress":      "status-in-progress",
    "Stuck":            "status-stuck",
    "FYI Only":         "status-fyi",
    # Silent-comms-derived statuses (from StatusUpdates tab):
    "Tricia on it":     "status-in-progress",
    "Maya on it":       "status-in-progress",
    "Approved":         "status-approval",
    "On Hold":          "status-in-progress",
    "Rejected":         "status-stuck",
    "Done":             "status-fyi",
    "Note added":       "status-fyi",
}

CATEGORY_TO_MARKER = {
    "Operations & Admin":      "OPERATIONS_ADMIN",
    "Leasing & Marketing":     "LEASING_MARKETING",
    "Maintenance & Repairs":   "MAINTENANCE_REPAIRS",
    "Financials & Accounting": "FINANCIALS_ACCOUNTING",
    "Tenant Relations":        "TENANT_RELATIONS",
}

MARKERS = {
    "QUICK_WINS":            ("<!-- QUICK_WINS_START -->",            "<!-- QUICK_WINS_END -->"),
    "OPERATIONS_ADMIN":      ("<!-- OPERATIONS_ADMIN_START -->",      "<!-- OPERATIONS_ADMIN_END -->"),
    "LEASING_MARKETING":     ("<!-- LEASING_MARKETING_START -->",     "<!-- LEASING_MARKETING_END -->"),
    "MAINTENANCE_REPAIRS":   ("<!-- MAINTENANCE_REPAIRS_START -->",   "<!-- MAINTENANCE_REPAIRS_END -->"),
    "FINANCIALS_ACCOUNTING": ("<!-- FINANCIALS_ACCOUNTING_START -->", "<!-- FINANCIALS_ACCOUNTING_END -->"),
    "TENANT_RELATIONS":      ("<!-- TENANT_RELATIONS_START -->",      "<!-- TENANT_RELATIONS_END -->"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def html_escape(text):
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def authenticate():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS env var not set")
    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def find_header_row(rows, header_hints=("Task / Issue", "Task", "Property")):
    """Locate the header row; tolerant of a banner row above headers."""
    for idx, row in enumerate(rows):
        for hint in header_hints:
            if hint in row:
                return idx, row
    return -1, None


def row_to_dict(headers, row):
    return {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)}


def get_task_id(row_dict, header_row_idx, row_idx, prefix=""):
    """
    Produce a stable task ID using the spreadsheet's '#' or 'ID' column when
    available, else a deterministic fallback derived from the row position.
    """
    for key in ("#", "ID", "Id", "id"):
        if key in row_dict and str(row_dict[key]).strip():
            return str(row_dict[key]).strip()
    # Fallback: sheet row number (1-indexed in spreadsheet; +1 for header row)
    return f"row-{header_row_idx + row_idx + 2}"


# ---------------------------------------------------------------------------
# Sheet fetchers
# ---------------------------------------------------------------------------
def fetch_operations_log(client):
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(OPS_LOG_TAB)
    all_values = ws.get_all_values()

    header_idx, headers = find_header_row(all_values)
    if not headers:
        print("  WARNING: header row not found in Operations Log")
        return defaultdict(lambda: defaultdict(list))

    grouped = defaultdict(lambda: defaultdict(list))

    for offset, row in enumerate(all_values[header_idx + 1:]):
        if not any(row):
            continue
        rd = row_to_dict(headers, row)
        task = rd.get("Task / Issue", "").strip()
        if not task:
            continue
        status = rd.get("Status", "").strip()
        if status not in VALID_STATUSES:
            continue
        category = rd.get("Category", "").strip() or "General"

        grouped[category][status].append({
            "id":       get_task_id(rd, header_idx, offset, prefix=""),
            "property": rd.get("Property", "").strip(),
            "task":     task,
            "notes":    rd.get("Notes", "").strip(),
            "assigned": rd.get("Assigned To", "").strip(),
            "priority": rd.get("Priority", "").strip(),
            "category": category,
            "status":   status,
        })
    return grouped


def fetch_archive(client, limit=9):
    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(ARCHIVE_TAB)
    except Exception:
        # Some sheets have the archive named without the emoji
        try:
            ws = sheet.worksheet("Archive")
        except Exception:
            print(f"  WARNING: Archive tab not found")
            return []
    all_values = ws.get_all_values()
    header_idx, headers = find_header_row(all_values)
    if not headers:
        return []
    items = []
    for row in reversed(all_values[header_idx + 1:]):
        if not any(row):
            continue
        rd = row_to_dict(headers, row)
        task = rd.get("Task / Issue", "").strip() or rd.get("Task", "").strip()
        if not task:
            continue
        items.append({
            "property": rd.get("Property", "").strip(),
            "task":     task,
            "notes":    rd.get("Notes", "").strip(),
        })
        if len(items) >= limit:
            break
    return items


def fetch_status_updates(client):
    """
    Return {id: {status, note, by, at}} of the LATEST entry per id from the
    StatusUpdates tab. If the tab is missing or empty, return {}.
    """
    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(STATUS_UPDATES_TAB)
    except Exception:
        print(f"  INFO: '{STATUS_UPDATES_TAB}' tab not found yet — nothing to overlay")
        return {}
    rows = ws.get_all_values()
    if len(rows) < 2:
        return {}
    headers = [h.strip().lower() for h in rows[0]]
    def col(name, default):
        return headers.index(name) if name in headers else default
    i_ts, i_id, i_st, i_note, i_by = (
        col("timestamp", 0), col("id", 1), col("status", 2),
        col("note", 3),     col("by", 4),
    )
    latest = {}
    for row in rows[1:]:
        if len(row) <= i_id or not row[i_id].strip():
            continue
        item_id = row[i_id].strip()
        ts_raw = row[i_ts] if i_ts < len(row) else ""
        # Sheets returns dates as strings — best-effort parse
        ts = ts_raw
        existing = latest.get(item_id)
        if existing and existing.get("at", "") >= ts:
            continue
        latest[item_id] = {
            "status": (row[i_st]   if i_st   < len(row) else "").strip(),
            "note":   (row[i_note] if i_note < len(row) else "").strip(),
            "by":     (row[i_by]   if i_by   < len(row) else "").strip(),
            "at":     ts,
        }
    return latest


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------
def build_task_item(task, latest_update):
    """
    Render a single task tile. All buttons are PLAIN — no inline onclick.
    The widget script (status-widget-client.js) will bind click handlers
    based on button class.
    """
    item_id      = task["id"]
    property_val = html_escape(task.get("property", ""))
    task_text    = html_escape(task.get("task", ""))
    notes_text   = html_escape(task.get("notes", ""))
    status       = task.get("status", "")

    overlay_note = ""
    overlay_by   = ""
    if latest_update:
        ov_status = latest_update.get("status", "")
        if ov_status and ov_status != status:
            status = ov_status
        overlay_note = html_escape(latest_update.get("note", ""))
        overlay_by   = html_escape(latest_update.get("by", ""))

    status_class = STATUS_CLASS_MAP.get(status, "status-fyi")

    # Action area depends on the original task's status meaning
    raw_status = task.get("status", "")
    parts = []
    parts.append(f'<div class="task-item" data-id="{html_escape(item_id)}">')
    parts.append( '    <div class="task-row">')
    parts.append( '        <div class="task-info">')
    parts.append( '            <button class="task-expand-btn">▼</button>')
    parts.append(f'            <div class="task-title">{task_text}</div>')
    if property_val:
        parts.append(f'            <div class="task-property">{property_val}</div>')
    parts.append( '        </div>')
    parts.append( '        <div class="task-status">')
    parts.append(f'            <div class="task-status-badge {status_class}">{html_escape(status)}</div>')
    parts.append( '        </div>')
    parts.append( '    </div>')
    parts.append( '    <div class="task-expanded">')
    if notes_text:
        parts.append(f'        <div class="task-description">{notes_text}</div>')
    if overlay_note:
        meta = f"Latest note from {overlay_by or 'someone'}: {overlay_note}"
        parts.append(f'        <div class="task-description" style="opacity:.85;font-style:italic">{meta}</div>')
    parts.append( '        <div class="task-actions">')
    parts.append( '            <div class="task-buttons">')

    if raw_status == "Needs Approval":
        parts.append('                <button class="btn-outlined btn-approve">Approve</button>')
        parts.append('                <button class="btn-outlined btn-hold">Hold Off</button>')
        parts.append('                <button class="btn-outlined btn-reject">Rejected</button>')
    elif raw_status in ("New", "In Progress", "FYI Only", "Maya Needs Help", "Stuck"):
        if raw_status in ("New", "Stuck", "Maya Needs Help"):
            parts.append('                <button class="btn-outlined btn-tricia">Tricia on it</button>')
            parts.append('                <button class="btn-outlined btn-maya">Maya on it</button>')
        # Always include a Done checkbox
        parts.append( '                <div class="checkbox-container">')
        parts.append(f'                    <input type="checkbox" id="cb-{html_escape(item_id)}" class="task-checkbox">')
        parts.append(f'                    <label for="cb-{html_escape(item_id)}" class="checkbox-label">')
        parts.append( '                        <div class="checkbox-box">')
        parts.append( '                            <div class="checkbox-fill"></div>')
        parts.append( '                            <div class="checkmark">')
        parts.append( '                                <svg class="check-icon" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>')
        parts.append( '                            </div>')
        parts.append( '                            <div class="success-ripple"></div>')
        parts.append( '                        </div>')
        parts.append( '                        <span class="checkbox-text">Done</span>')
        parts.append( '                    </label>')
        parts.append( '                </div>')

    parts.append( '            </div>')
    parts.append( '            <div style="display: flex; flex-direction: column; gap: 8px;">')
    placeholder = "Leave a quick note (auto-saves when you click Save Note)..."
    parts.append(f'                <textarea class="task-comment-input" placeholder="{placeholder}">{overlay_note}</textarea>')
    parts.append( '                <button class="comment-save-btn">Save Note</button>')
    parts.append( '            </div>')
    parts.append( '        </div>')
    parts.append( '    </div>')
    parts.append( '</div>')
    return "\n".join(parts)


def build_quick_wins(archive_items):
    if not archive_items:
        return '<div class="empty-state">No recent completions</div>'
    out = []
    for it in archive_items:
        text = html_escape(it.get("task", ""))
        if len(text) > 75:
            text = text[:72] + "..."
        out.append(
            '<div class="win-item">\n'
            '    <div class="win-check">✓</div>\n'
            f'   <div class="win-item-text">{text}</div>\n'
            '</div>'
        )
    return "\n".join(out)


def inject_into_template(template_html, ops_grouped, archive_items, status_overlay):
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    html = template_html.replace("<!-- LAST_UPDATED -->", now)

    # Build per-category content
    for category, marker_key in CATEGORY_TO_MARKER.items():
        content = ""
        if category in ops_grouped:
            for status in STATUS_ORDER:
                for task in ops_grouped[category].get(status, []):
                    overlay = status_overlay.get(task["id"])
                    content += build_task_item(task, overlay) + "\n\n"
            for status in ops_grouped[category]:
                # render Needs Approval too (not in STATUS_ORDER)
                if status not in STATUS_ORDER:
                    for task in ops_grouped[category].get(status, []):
                        overlay = status_overlay.get(task["id"])
                        content += build_task_item(task, overlay) + "\n\n"
        if not content.strip():
            content = '                <div class="empty-state">No items in this category</div>'
        else:
            content = "\n".join("                " + line if line.strip() else line for line in content.split("\n"))

        start, end = MARKERS[marker_key]
        pattern = re.escape(start) + r".*?" + re.escape(end)
        replacement = f"{start}\n{content}\n                {end}"
        if re.search(pattern, html, re.DOTALL):
            html = re.sub(pattern, replacement, html, flags=re.DOTALL)
        else:
            print(f"  WARNING: {marker_key} markers not found")

    # Quick wins
    wins = build_quick_wins(archive_items)
    wins_indented = "\n".join("                " + line if line.strip() else line for line in wins.split("\n"))
    start, end = MARKERS["QUICK_WINS"]
    pattern = re.escape(start) + r".*?" + re.escape(end)
    replacement = f"{start}\n{wins_indented}\n                {end}"
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("TPS Dashboard Generator")
    print("=" * 50)

    print("Authenticating...")
    client = authenticate()

    print("Reading Operations Log...")
    ops_grouped = fetch_operations_log(client)
    total_ops = sum(sum(len(v) for v in s.values()) for s in ops_grouped.values())
    print(f"  Found {total_ops} active tasks")

    print("Reading Archive...")
    archive_items = fetch_archive(client, limit=9)
    print(f"  Found {len(archive_items)} archived items")

    print("Reading StatusUpdates...")
    status_overlay = fetch_status_updates(client)
    print(f"  Found {len(status_overlay)} silent-comms entries to overlay")

    print(f"Reading template from {TEMPLATE_HTML}...")
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
        template_html = f.read()

    print("Generating HTML...")
    new_html = inject_into_template(template_html, ops_grouped, archive_items, status_overlay)

    print(f"Writing {INDEX_HTML}...")
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("=" * 50)
    print(f"Dashboard refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
        raise
