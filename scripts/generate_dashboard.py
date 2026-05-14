#!/usr/bin/env python3
"""
TPS Daily Dashboard Generator - FINAL VERSION
Reads Google Sheets Operations Log + Archive, generates fresh index.html
Runs daily at 7 AM via GitHub Actions

Features:
- Reads Operations Log (Date, Property, Task/Issue, Notes, Category, Priority, Assigned To, Status)
- Filters by status: New, In Progress, Stuck, Needs Approval, Maya Needs Help
- Generates status-specific buttons and controls
- Intelligently summarizes Quick Wins from Archive (last 7 days)
- Truncates notes with click-to-expand capability
- Includes subtle priority badges
"""

import os
import json
import re
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_LOG_TAB = "Operations Log"
ARCHIVE_TAB = "📦 Archive"
INDEX_HTML = "index.html"

# Column indices (0-based) for Operations Log
OPS_COLS = {
    "date": 0,
    "property": 1,
    "task": 2,
    "notes": 3,
    "category": 4,
    "priority": 5,
    "assigned": 6,
    "status": 7,
}

# Column indices for Archive
ARC_COLS = {
    "date": 0,
    "property": 1,
    "task": 2,
    "notes": 3,
    "category": 4,
    "priority": 5,
    "assigned": 6,
    "status": 7,
    "date_completed": 8,
}

def authenticate():
    """Authenticate with Google Sheets API using service account."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set")

    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def safe_get(row, col, default=""):
    """Safely get a column value from a row."""
    try:
        val = row[col] if col < len(row) else default
        return str(val).strip() if val else default
    except (IndexError, TypeError):
        return default

def html_escape(text):
    """Escape HTML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

def truncate_notes(notes, max_length=100):
    """Truncate notes and return truncated + full versions."""
    if len(notes) <= max_length:
        return notes, notes
    truncated = notes[:max_length].rsplit(' ', 1)[0] + "..."
    return truncated, notes

def extract_priority_class(priority):
    """Extract priority level from priority string and return CSS class."""
    priority_lower = priority.lower()
    if "🔴" in priority or "high" in priority_lower:
        return "priority-high"
    elif "🟡" in priority or "medium" in priority_lower:
        return "priority-medium"
    elif "🟢" in priority or "low" in priority_lower:
        return "priority-low"
    return "priority-low"

def get_priority_label(priority):
    """Extract priority label from priority string."""
    if "high" in priority.lower() or "🔴" in priority:
        return "High"
    elif "medium" in priority.lower() or "🟡" in priority:
        return "Medium"
    elif "low" in priority.lower() or "🟢" in priority:
        return "Low"
    return "Medium"

def intelligently_summarize_win(property_addr, task, notes, assigned):
    """
    Intelligently summarize a completed item from Archive.
    Extract key action words: Approved, Paid, Scheduled, Completed, Notified, Canceled
    """
    task_lower = task.lower()
    notes_lower = notes.lower()

    # Action indicators mapping
    action_indicators = {
        "approved": "Approved",
        "paid": "Paid",
        "processed": "Paid",
        "scheduled": "Scheduled",
        "completed": "Completed",
        "notified": "Notified",
        "canceled": "Canceled",
        "cancelled": "Canceled",
    }

    # Find the action that applies
    action = None
    for key, label in action_indicators.items():
        if key in notes_lower or key in task_lower:
            action = label
            break

    # Build summary
    summary = task.strip()

    # Add property if not "General"
    if property_addr and property_addr.lower() != "general":
        summary = f"{property_addr} — {summary}"

    # Add action if found
    if action:
        summary = f"{summary} — {action}"

    return summary.strip()

def fetch_operations_log(client):
    """Read Operations Log sheet and return list of task dicts organized by status."""
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(OPS_LOG_TAB)
    rows = ws.get_all_values()

    tasks_by_status = {
        "needs_approval": [],
        "in_progress": [],
        "new": [],
        "stuck": [],
        "maya_needs_help": []
    }

    # Skip header rows (first 2 rows)
    for row in rows[2:]:
        if not any(row):
            continue

        property_addr = safe_get(row, OPS_COLS["property"])
        task = safe_get(row, OPS_COLS["task"])
        notes = safe_get(row, OPS_COLS["notes"])
        assigned = safe_get(row, OPS_COLS["assigned"])
        status = safe_get(row, OPS_COLS["status"])
        priority = safe_get(row, OPS_COLS["priority"])

        # Skip if empty task
        if not task:
            continue

        # Truncate notes
        notes_truncated, notes_full = truncate_notes(notes, 100)

        task_obj = {
            "property": property_addr,
            "task": task,
            "notes": notes,
            "notes_truncated": notes_truncated,
            "notes_full": notes_full,
            "assigned": assigned,
            "status": status.lower(),
            "priority": priority,
            "priority_class": extract_priority_class(priority),
            "priority_label": get_priority_label(priority),
        }

        # Organize by status
        status_lower = status.lower()
        if "needs approval" in status_lower:
            tasks_by_status["needs_approval"].append(task_obj)
        elif "in progress" in status_lower:
            tasks_by_status["in_progress"].append(task_obj)
        elif "stuck" in status_lower:
            tasks_by_status["stuck"].append(task_obj)
        elif "maya needs help" in status_lower:
            tasks_by_status["maya_needs_help"].append(task_obj)
        elif "new" in status_lower:
            tasks_by_status["new"].append(task_obj)

    return tasks_by_status

def fetch_archive(client, days=7):
    """Read Archive sheet and return recently completed items with smart summaries."""
    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(ARCHIVE_TAB)
    except:
        print("  WARNING: Archive sheet not found")
        return []

    rows = ws.get_all_values()
    cutoff = datetime.now() - timedelta(days=days)
    items = []

    for row in rows[2:]:  # Skip headers
        if not any(row):
            continue

        task = safe_get(row, ARC_COLS["task"])
        if not task:
            continue

        # Try to parse date completed (column K = index 10)
        date_str = safe_get(row, 10) if len(row) > 10 else ""
        item_date = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                item_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue

        # Include if within cutoff
        if item_date and item_date >= cutoff:
            property_addr = safe_get(row, ARC_COLS["property"])
            notes = safe_get(row, ARC_COLS["notes"])
            assigned = safe_get(row, ARC_COLS["assigned"])

            # Create smart summary
            summary = intelligently_summarize_win(property_addr, task, notes, assigned)

            items.append({
                "property": property_addr,
                "task": task,
                "notes": notes,
                "assigned": assigned,
                "date": date_str,
                "summary": summary,
            })

    # Sort by date, newest first
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items  # Return all items from last 7 days (no limit)

def build_task_card(task, status_type):
    """Generate HTML for a single task card based on status type."""
    property_val = html_escape(task["property"])
    task_desc = html_escape(task["task"])
    notes_trunc = html_escape(task["notes_truncated"])
    assigned = html_escape(task["assigned"])
    priority_class = task["priority_class"]
    priority_label = task["priority_label"]

    # Build task-top section
    task_top = (
        f'        <div class="task-top">\n'
        f'          <div class="task-left">\n'
        f'            <div class="task-property">{property_val}</div>\n'
        f'            <div class="task-description">{task_desc}</div>\n'
        f'            <div class="task-notes"><span class="note-truncated">{notes_trunc}</span></div>\n'
        f'          </div>\n'
        f'          <div class="task-right">\n'
        f'            <div class="task-meta">\n'
        f'              <span class="priority-badge {priority_class}">{priority_label}</span>\n'
    )

    # Status badge and assigned info varies by status
    if status_type == "needs_approval":
        task_top += f'              <span class="status-badge approval">Approval</span>\n'
    elif status_type == "in_progress":
        task_top += f'              <span class="status-badge inprogress">In Progress</span>\n'
    elif status_type == "new":
        task_top += f'              <span class="status-badge new">New</span>\n'
    elif status_type == "stuck":
        task_top += f'              <span class="status-badge stuck">Stuck</span>\n'
    elif status_type == "maya_needs_help":
        task_top += f'              <span class="status-badge help">Maya Needs Help</span>\n'

    task_top += f'            </div>\n'

    # Show assigned for In Progress and Needs Approval, but not for New
    if status_type in ("in_progress", "needs_approval", "stuck", "maya_needs_help"):
        task_top += f'            <span class="assigned">👤 {assigned}</span>\n'

    task_top += f'          </div>\n        </div>\n'

    # Build controls based on status
    controls = ""
    if status_type == "needs_approval":
        controls = (
            f'        <div class="task-controls">\n'
            f'          <div class="btn-group">\n'
            f'            <button>Approved</button>\n'
            f'            <button>On Hold</button>\n'
            f'            <button>Rejected</button>\n'
            f'          </div>\n'
            f'          <div class="task-note"><input type="text" placeholder="Add note..."></div>\n'
            f'        </div>\n'
        )
    elif status_type == "in_progress":
        controls = (
            f'        <div class="task-controls">\n'
            f'          <div class="btn-group">\n'
            f'            <button>Done</button>\n'
            f'          </div>\n'
            f'          <div class="task-note"><input type="text" placeholder="Add note..."></div>\n'
            f'        </div>\n'
        )
    elif status_type == "new":
        controls = (
            f'        <div class="task-controls">\n'
            f'          <div class="btn-group">\n'
            f'            <button>Maya on it</button>\n'
            f'            <button>Tricia on it</button>\n'
            f'            <button>Done</button>\n'
            f'          </div>\n'
            f'          <div class="task-note"><input type="text" placeholder="Add note..."></div>\n'
            f'        </div>\n'
        )
    elif status_type in ("stuck", "maya_needs_help"):
        controls = (
            f'        <div class="task-controls">\n'
            f'          <div class="task-note"><input type="text" placeholder="Add note..."></div>\n'
            f'        </div>\n'
        )

    return (
        f'        <div class="task-card">\n'
        f'{task_top}'
        f'{controls}'
        f'        </div>'
    )

def build_wins_grid(archive_items):
    """Generate grid items for Quick Wins section using smart summaries (3-column grid)."""
    items = []
    for item in archive_items:
        summary = html_escape(item["summary"])
        items.append(f'                <div class="wins-item">{summary}</div>')
    return '\n'.join(items)

def inject_into_html(tasks_by_status, archive_items):
    """Inject generated content into index.html between markers."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p EDT")

    # Generate task cards by status
    approvals_html = '\n'.join(build_task_card(t, "needs_approval") for t in tasks_by_status["needs_approval"])
    inprogress_html = '\n'.join(build_task_card(t, "in_progress") for t in tasks_by_status["in_progress"])
    new_html = '\n'.join(build_task_card(t, "new") for t in tasks_by_status["new"])
    stuck_html = '\n'.join(build_task_card(t, "stuck") for t in tasks_by_status["stuck"])
    help_html = '\n'.join(build_task_card(t, "maya_needs_help") for t in tasks_by_status["maya_needs_help"])

    wins_html = build_wins_grid(archive_items)

    # Inject approvals
    pattern = r'<!-- OPS-LOG-APPROVALS-START -->.*?<!-- OPS-LOG-APPROVALS-END -->'
    block = f'<!-- OPS-LOG-APPROVALS-START -->\n                <!-- Updated {now} -->\n{approvals_html}\n                <!-- OPS-LOG-APPROVALS-END -->'
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, block, html, flags=re.DOTALL)
    else:
        print("  WARNING: OPS-LOG-APPROVALS markers not found")

    # Inject in progress
    pattern = r'<!-- OPS-LOG-INPROGRESS-START -->.*?<!-- OPS-LOG-INPROGRESS-END -->'
    block = f'<!-- OPS-LOG-INPROGRESS-START -->\n                <!-- Updated {now} -->\n{inprogress_html}\n                <!-- OPS-LOG-INPROGRESS-END -->'
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, block, html, flags=re.DOTALL)
    else:
        print("  WARNING: OPS-LOG-INPROGRESS markers not found")

    # Inject new items
    pattern = r'<!-- OPS-LOG-NEW-START -->.*?<!-- OPS-LOG-NEW-END -->'
    block = f'<!-- OPS-LOG-NEW-START -->\n                <!-- Updated {now} -->\n{new_html}\n                <!-- OPS-LOG-NEW-END -->'
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, block, html, flags=re.DOTALL)
    else:
        print("  WARNING: OPS-LOG-NEW markers not found")

    # Inject quick wins
    pattern = r'<!-- ARCHIVE-START -->.*?<!-- ARCHIVE-END -->'
    block = f'<!-- ARCHIVE-START -->\n                <!-- Updated {now} -->\n{wins_html}\n                <!-- ARCHIVE-END -->'
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, block, html, flags=re.DOTALL)
    else:
        print("  WARNING: ARCHIVE markers not found")

    # Update timestamp in page
    pattern = r'(<p class="last-updated">)[^<]*(</p>)'
    replacement = rf'\g<1>Closed items — {now}\g<2>'
    html = re.sub(pattern, replacement, html)

    # Write updated HTML
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    total_tasks = sum(len(v) for v in tasks_by_status.values())
    print(f"✓ Dashboard updated: {len(tasks_by_status['needs_approval'])} approvals, {len(tasks_by_status['in_progress'])} in progress, {len(tasks_by_status['new'])} new, {len(archive_items)} wins")

def main():
    print("🔄 TPS Dashboard Generator (FINAL)")
    print("=" * 50)

    try:
        print("Authenticating with Google Sheets...")
        client = authenticate()

        print("Reading Operations Log...")
        ops = fetch_operations_log(client)
        total_ops = sum(len(v) for v in ops.values())
        print(f"  Found {total_ops} tasks")

        print("Reading Archive (last 7 days with smart summaries)...")
        arc = fetch_archive(client, days=7)
        print(f"  Found {len(arc)} recent completions")
        for item in arc[:3]:
            print(f"    → {item['summary']}")

        print("Generating HTML...")
        inject_into_html(ops, arc)

        print("=" * 50)
        print("✓ Done! Dashboard is fresh and ready.")

    except Exception as e:
        print(f"✗ Error: {e}")
        raise

if __name__ == "__main__":
    main()