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
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_LOG_TAB = "Operations Log"
ARCHIVE_TAB = "Archive"
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

    # Get all values as raw data
    all_values = ws.get_all_values()

    # Find header row (contains "Task / Issue")
    header_idx = 0
    headers = None
    for idx, row in enumerate(all_values):
        if "Task / Issue" in row:
            header_idx = idx
            headers = row
            break

    if not headers:
        print("  WARNING: Could not find header row with 'Task / Issue'")
        return {
            STATUS_NEEDS_APPROVAL: [],
            STATUS_MAYA_NEEDS_HELP: [],
            STATUS_NEW: [],
            STATUS_IN_PROGRESS: [],
            STATUS_STUCK: [],
            STATUS_FYI_ONLY: [],
        }

    # Initialize status categories
    tasks_by_status = {
        STATUS_NEEDS_APPROVAL: [],
        STATUS_MAYA_NEEDS_HELP: [],
        STATUS_NEW: [],
        STATUS_IN_PROGRESS: [],
        STATUS_STUCK: [],
        STATUS_FYI_ONLY: [],
    }

    # Process data rows (skip header and everything before it)
    for row in all_values[header_idx + 1:]:
        if not any(row):  # Skip completely empty rows
            continue

        # Create a dict from headers and row values
        row_dict = {}
        for i, header in enumerate(headers):
            row_dict[header] = row[i] if i < len(row) else ""

        # Skip if no task
        task = row_dict.get("Task / Issue", "").strip()
        if not task:
            continue

        status = row_dict.get("Status", "").strip()
        if status not in tasks_by_status:
            continue  # Skip items with unknown status

        task_data = {
            "property": row_dict.get("Property", "").strip(),
            "task": task,
            "notes": row_dict.get("Notes", "").strip(),
            "assigned": row_dict.get("Assigned To", "").strip(),
            "priority": row_dict.get("Priority", "").strip(),
            "category": row_dict.get("Category", "").strip(),
            "status": status,
        }

        tasks_by_status[status].append(task_data)

    return tasks_by_status

def fetch_archive(client, limit=9):
    """Read Archive sheet and return last N items (newest first)."""
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(ARCHIVE_TAB)

    # Get all values as raw data
    all_values = ws.get_all_values()

    # Find header row
    header_idx = 0
    headers = None
    for idx, row in enumerate(all_values):
        if "Task / Issue" in row or "Task" in row:
            header_idx = idx
            headers = row
            break

    if not headers:
        print("  WARNING: Could not find header row in Archive sheet")
        return []

    items = []
    # Process data rows in reverse order (newest first)
    for row in reversed(all_values[header_idx + 1:]):
        if not any(row):  # Skip empty rows
            continue

        # Create a dict from headers and row values
        row_dict = {}
        for i, header in enumerate(headers):
            row_dict[header] = row[i] if i < len(row) else ""

        # Skip if no task
        task = row_dict.get("Task / Issue", "").strip()
        if not task:
            continue

        items.append({
            "property": row_dict.get("Property", "").strip(),
            "task": task,
            "notes": row_dict.get("Notes", "").strip(),
            "assigned": row_dict.get("Assigned To", "").strip(),
            "priority": row_dict.get("Priority", "").strip(),
            "category": row_dict.get("Category", "").strip(),
        })

        if len(items) >= limit:
            break

    return items

def build_task_item(task, item_id=None):
    """Generate HTML for a task item in a section (new dashboard format)."""
    property_val = html_escape(task.get("property", ""))
    task_text = html_escape(task.get("task", ""))
    notes_text = html_escape(task.get("notes", ""))
    assigned = html_escape(task.get("assigned", ""))
    priority = html_escape(task.get("priority", ""))
    status = task.get("status", "")

    # Generate a simple ID if not provided
    if not item_id:
        item_id = f"task-{task_text[:10].replace(' ', '-')}"

    # Build priority class (map to High/Medium/Low)
    priority_class = "medium"
    if priority:
        priority_clean = priority.lower()
        if "high" in priority_clean or "🔴" in priority:
            priority_class = "high"
        elif "low" in priority_clean or "🟢" in priority:
            priority_class = "low"
        elif "medium" in priority_clean or "🟡" in priority:
            priority_class = "medium"

    # Status class mapping
    status_class_map = {
        "Needs Approval": "status-approval",
        "Maya Needs Help": "status-maya-help",
        "New": "status-new",
        "In Progress": "status-in-progress",
        "Stuck": "status-stuck",
        "FYI Only": "status-fyi",
    }
    status_class = status_class_map.get(status, "status-fyi")

    html = f'            <div class="task-card">\n'
    html += f'                <input type="checkbox" class="task-checkbox" onchange="toggleDescription(\'{item_id}\')">\n'
    html += f'                <div class="task-info">\n'
    if property_val:
        html += f'                    <div class="task-location">{property_val}</div>\n'
    html += f'                    <div class="task-title">{task_text}</div>\n'
    if notes_text:
        html += f'                    <div class="task-description" id="desc-{item_id}">{notes_text}</div>\n'
    html += f'                </div>\n'
    html += f'                <div class="task-right">\n'
    html += f'                    <div class="priority-dot priority-{priority_class}"></div>\n'
    html += f'                    <div class="task-status-badge {status_class}">{status}</div>\n'
    html += f'                </div>\n'
    html += f'            </div>\n'

    return html

def build_quick_wins(archive_items):
    """Generate HTML for Quick Wins section from archive items."""
    if not archive_items:
        return '                <li>No recent completions</li>'

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

        items.append(f'                <li>{label}</li>')

    return '\n'.join(items)

def inject_into_html(ops_tasks_by_status, archive_items):
    """Inject generated content into index.html between markers."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Build HTML for each status category
    def build_section(tasks, status_name):
        html = ""
        for idx, task in enumerate(tasks):
            item_id = f"{status_name.lower()}-{idx}"
            html += build_task_item(task, item_id)
        return html

    sections = {
        "NEEDS_APPROVAL": build_section(ops_tasks_by_status[STATUS_NEEDS_APPROVAL], "approval"),
        "MAYA_NEEDS_HELP": build_section(ops_tasks_by_status[STATUS_MAYA_NEEDS_HELP], "maya"),
        "NEW_ITEMS": build_section(ops_tasks_by_status[STATUS_NEW], "new"),
        "IN_PROGRESS": build_section(ops_tasks_by_status[STATUS_IN_PROGRESS], "progress"),
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
