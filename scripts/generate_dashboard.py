#!/usr/bin/env python3
"""
TPS Daily Dashboard Generator
Reads Google Sheets Operations Log + Archive, generates fresh index.html
Runs daily at 7 AM EDT (11 AM UTC) via GitHub Actions

Columns (A-I):
  A: # (ID)
  B: Date
  C: Property
  D: Task / Issue
  E: Notes
  F: Category
  G: Priority
  H: Assigned To
  I: Status
"""

import os
import json
import re
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1G2JYQp-zvGEHEbBIJuniRG3itq0ysNdOGuVsy-WGKg4")
OPS_LOG_TAB = "Operations Log"
ARCHIVE_TAB = "📦 Archive"
INDEX_HTML = "index.html"

# Status values (exact match from sheet)
STATUS_NEEDS_APPROVAL = "Needs Approval"
STATUS_MAYA_NEEDS_HELP = "Maya Needs Help"
STATUS_NEW = "New"
STATUS_IN_PROGRESS = "In Progress"
STATUS_STUCK = "Stuck"
STATUS_FYI_ONLY = "FYI Only"

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

def html_escape(text):
    """Escape HTML special characters."""
    if not text:
        return ""
    return (str(text).replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace('"', "&quot;"))

def fetch_operations_log(client):
    """Read Operations Log sheet and return tasks grouped by status."""
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(OPS_LOG_TAB)

    # Get all values to find the actual header row (skip decorative/blank rows)
    all_values = ws.get_all_values()

    # Find the row with actual headers (contains "Task / Issue" or similar)
    header_row_idx = 0
    for idx, row in enumerate(all_values):
        if any("Task" in str(cell) or "Status" in str(cell) for cell in row):
            header_row_idx = idx
            break

    # Get records starting from the actual header row
    rows = ws.get_all_records(expected_headers=all_values[header_row_idx])

    # Initialize status categories
    tasks_by_status = {
        STATUS_NEEDS_APPROVAL: [],
        STATUS_MAYA_NEEDS_HELP: [],
        STATUS_NEW: [],
        STATUS_IN_PROGRESS: [],
        STATUS_STUCK: [],
        STATUS_FYI_ONLY: [],
    }

    for row in rows:
        # Skip empty rows
        if not row.get("Task / Issue"):
            continue

        status = row.get("Status", "").strip()
        if status not in tasks_by_status:
            continue  # Skip items with unknown status

        task_data = {
            "property": row.get("Property", "").strip(),
            "task": row.get("Task / Issue", "").strip(),
            "notes": row.get("Notes", "").strip(),
            "assigned": row.get("Assigned To", "").strip(),
            "priority": row.get("Priority", "").strip(),
            "category": row.get("Category", "").strip(),
            "status": status,
        }

        tasks_by_status[status].append(task_data)

    return tasks_by_status

def fetch_archive(client, limit=9):
    """Read Archive sheet and return last N items (newest first)."""
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(ARCHIVE_TAB)

    # Get all values to find the actual header row (skip decorative/blank rows)
    all_values = ws.get_all_values()

    # Find the row with actual headers
    header_row_idx = 0
    for idx, row in enumerate(all_values):
        if any("Task" in str(cell) or "Status" in str(cell) for cell in row):
            header_row_idx = idx
            break

    # Get records starting from the actual header row
    rows = ws.get_all_records(expected_headers=all_values[header_row_idx])

    items = []
    for row in reversed(rows):  # Reverse to get newest first
        if not row.get("Task / Issue"):
            continue

        items.append({
            "property": row.get("Property", "").strip(),
            "task": row.get("Task / Issue", "").strip(),
            "notes": row.get("Notes", "").strip(),
            "assigned": row.get("Assigned To", "").strip(),
            "priority": row.get("Priority", "").strip(),
            "category": row.get("Category", "").strip(),
        })

        if len(items) >= limit:
            break

    return items

def build_task_item(task):
    """Generate HTML for a task item in a section."""
    property_val = html_escape(task.get("property", ""))
    task_text = html_escape(task.get("task", ""))
    assigned = html_escape(task.get("assigned", ""))
    priority = html_escape(task.get("priority", ""))

    # Build title
    title = f"{task_text}"
    if property_val:
        title = f"[{property_val}] {task_text}"

    # Build metadata
    meta = []
    if priority:
        meta.append(f"Priority: {priority}")
    if assigned:
        meta.append(f"Assigned: {assigned}")
    meta_str = " | ".join(meta) if meta else ""

    html = f'            <div class="task-item">\n'
    html += f'                <div class="task-title">{title}</div>\n'
    if meta_str:
        html += f'                <div class="task-meta">{meta_str}</div>\n'
    html += f'            </div>\n'

    return html

def build_quick_wins(archive_items):
    """Generate HTML for Quick Wins section from archive items."""
    if not archive_items:
        return '<p style="color: #999;">No recent completions</p>'

    items = []
    for item in archive_items:
        property_val = html_escape(item.get("property", ""))
        task_text = html_escape(item.get("task", ""))
        assigned = html_escape(item.get("assigned", ""))

        # Build label intelligently
        label = task_text
        if property_val and property_val.lower() not in ("general", "n/a", ""):
            label = f"{property_val} — {task_text}"

        if len(label) > 60:
            label = label[:57] + "..."

        if assigned:
            label += f" ({assigned})"

        items.append(f'            <div class="quick-win-item">{label}</div>')

    return '\n'.join(items)

def inject_into_html(ops_tasks_by_status, archive_items):
    """Inject generated content into index.html between markers."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Build HTML for each status category
    sections = {
        "NEEDS_APPROVAL": "".join(build_task_item(t) for t in ops_tasks_by_status[STATUS_NEEDS_APPROVAL]),
        "MAYA_NEEDS_HELP": "".join(build_task_item(t) for t in ops_tasks_by_status[STATUS_MAYA_NEEDS_HELP]),
        "NEW_ITEMS": "".join(build_task_item(t) for t in ops_tasks_by_status[STATUS_NEW]),
        "IN_PROGRESS": "".join(build_task_item(t) for t in ops_tasks_by_status[STATUS_IN_PROGRESS]),
        "QUICK_WINS": build_quick_wins(archive_items),
    }

    # Inject each section
    markers = {
        "NEEDS_APPROVAL": ("<!-- NEEDS_APPROVAL_START -->", "<!-- NEEDS_APPROVAL_END -->"),
        "MAYA_NEEDS_HELP": ("<!-- MAYA_NEEDS_HELP_START -->", "<!-- MAYA_NEEDS_HELP_END -->"),
        "NEW_ITEMS": ("<!-- NEW_ITEMS_START -->", "<!-- NEW_ITEMS_END -->"),
        "IN_PROGRESS": ("<!-- IN_PROGRESS_START -->", "<!-- IN_PROGRESS_END -->"),
        "QUICK_WINS": ("<!-- QUICK_WINS_START -->", "<!-- QUICK_WINS_END -->"),
    }

    for section, (start_marker, end_marker) in markers.items():
        pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
        content = sections.get(section, "")
        replacement = f"{start_marker}\n{content}\n            {end_marker}"

        if re.search(pattern, html, re.DOTALL):
            html = re.sub(pattern, replacement, html, flags=re.DOTALL)
        else:
            print(f"  WARNING: {section} markers not found in HTML")

    # Write updated HTML
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # Print summary
    total_count = sum(len(tasks) for tasks in ops_tasks_by_status.values())
    print(f"✓ Dashboard updated at {now}")
    print(f"  Needs Approval: {len(ops_tasks_by_status[STATUS_NEEDS_APPROVAL])}")
    print(f"  Maya Needs Help: {len(ops_tasks_by_status[STATUS_MAYA_NEEDS_HELP])}")
    print(f"  New: {len(ops_tasks_by_status[STATUS_NEW])}")
    print(f"  In Progress: {len(ops_tasks_by_status[STATUS_IN_PROGRESS])}")
    print(f"  Stuck: {len(ops_tasks_by_status[STATUS_STUCK])}")
    print(f"  FYI Only: {len(ops_tasks_by_status[STATUS_FYI_ONLY])}")
    print(f"  Quick Wins: {len(archive_items)}")

def main():
    print("🔄 TPS Dashboard Generator")
    print("=" * 50)

    try:
        print("Authenticating with Google Sheets...")
        client = authenticate()

        print("Reading Operations Log...")
        ops_by_status = fetch_operations_log(client)
        total_ops = sum(len(tasks) for tasks in ops_by_status.values())
        print(f"  Found {total_ops} tasks across all statuses")

        print("Reading Archive...")
        arc = fetch_archive(client, limit=9)
        print(f"  Found {len(arc)} archived items")

        print("Generating HTML...")
        inject_into_html(ops_by_status, arc)

        print("=" * 50)
        print("✓ Done! Dashboard is fresh.")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
