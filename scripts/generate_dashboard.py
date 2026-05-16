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
from collections import defaultdict
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_LOG_TAB = "Operations Log"
ARCHIVE_TAB = "📦 Archive"
INDEX_HTML = "index.html"

# Category and status order
CATEGORY_ORDER = ["Operations & Admin", "Leasing & Marketing", "Maintenance & Repairs", "Financials & Accounting", "Tenant Relations"]
STATUS_ORDER = ["Stuck", "Maya Needs Help", "New", "In Progress", "FYI Only"]

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
    """Read Operations Log sheet and return tasks grouped by category and status."""
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
        return defaultdict(lambda: defaultdict(list))

    # Initialize nested structure: {category: {status: [tasks]}}
    tasks_by_category_status = defaultdict(lambda: defaultdict(list))

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
        category = row_dict.get("Category", "").strip() or "General"

        # Skip if invalid status
        valid_statuses = [STATUS_NEEDS_APPROVAL, STATUS_MAYA_NEEDS_HELP, STATUS_NEW,
                         STATUS_IN_PROGRESS, STATUS_STUCK, STATUS_FYI_ONLY]
        if status not in valid_statuses:
            continue

        task_data = {
            "property": row_dict.get("Property", "").strip(),
            "task": task,
            "notes": row_dict.get("Notes", "").strip(),
            "assigned": row_dict.get("Assigned To", "").strip(),
            "priority": row_dict.get("Priority", "").strip(),
            "category": category,
            "status": status,
        }

        tasks_by_category_status[category][status].append(task_data)

    return tasks_by_category_status

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
    """Generate HTML for a task item in the new design."""
    property_val = html_escape(task.get("property", ""))
    task_text = html_escape(task.get("task", ""))
    notes_text = html_escape(task.get("notes", ""))
    priority = html_escape(task.get("priority", ""))
    assigned = html_escape(task.get("assigned", ""))
    status = task.get("status", "")

    # Generate a simple ID if not provided
    if not item_id:
        item_id = f"task-{task_text[:10].replace(' ', '-')}"

    # Build priority class and label
    priority_class = "medium"
    priority_label = "MEDIUM"
    if priority:
        priority_clean = priority.lower()
        if "high" in priority_clean:
            priority_class = "high"
            priority_label = "HIGH"
        elif "low" in priority_clean:
            priority_class = "low"
            priority_label = "LOW"
        elif "medium" in priority_clean:
            priority_class = "medium"
            priority_label = "MEDIUM"

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

    # Build task header
    html = f'            <div class="task-card">\n'
    html += f'                <div class="task-header">\n'
    html += f'                    <div class="task-info">\n'
    if property_val:
        html += f'                        <div class="task-location">{property_val}</div>\n'
    html += f'                        <div class="task-title">{task_text}</div>\n'
    if notes_text:
        html += f'                        <div class="task-description">{notes_text}</div>\n'
    html += f'                        <div class="task-meta">\n'
    html += f'                            <div class="priority-dot priority-{priority_class}"></div>\n'
    html += f'                            <span>{priority_label}</span>\n'
    if assigned:
        html += f'                            <span>• {assigned}</span>\n'
    html += f'                        </div>\n'
    html += f'                        <div class="task-status-badge {status_class}">{status}</div>\n'
    html += f'                    </div>\n'
    html += f'                </div>\n'

    # Build task controls based on status
    html += f'                <div class="task-controls">\n'

    if status == "Needs Approval":
        html += f'                    <div class="btn-group">\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'approved\', \'active-green\')">Approved</button>\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'on-hold\', \'active-yellow\')">On Hold</button>\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'rejected\', \'active-red\')">Rejected</button>\n'
        html += f'                    </div>\n'
    elif status == "New":
        html += f'                    <div class="btn-group">\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'tricia\', \'active-blue\')">Tricia on it</button>\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'maya\', \'active-blue\')">Maya on it</button>\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'done\', \'active-blue\')">Done</button>\n'
        html += f'                    </div>\n'
    elif status == "In Progress":
        html += f'                    <div class="btn-group">\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'done\', \'active-blue\')">Done</button>\n'
        html += f'                    </div>\n'
    elif status == "FYI Only":
        html += f'                    <div class="btn-group">\n'
        html += f'                        <button class="btn-control" onclick="setResponse(\'{item_id}\', this, \'done\', \'active-blue\')">Done</button>\n'
        html += f'                    </div>\n'
    # For "Stuck" and "Maya Needs Help", no buttons, just textarea

    html += f'                    <textarea class="comment-box" id="note-{item_id}" placeholder="Add a note..." onchange="updateNote(\'{item_id}\', this)"></textarea>\n'
    html += f'                </div>\n'
    html += f'            </div>\n'

    return html

def build_quick_wins(archive_items):
    """Generate HTML for Quick Wins section from archive items.
    Intelligently combines Task + Notes into concise summaries."""
    if not archive_items:
        return '                <li>No recent completions</li>'

    items = []
    for item in archive_items:
        property_val = html_escape(item.get("property", ""))
        task_text = html_escape(item.get("task", ""))
        notes_text = html_escape(item.get("notes", "")).strip()

        # Extract key info from task and notes
        # Remove common prefixes (Process, Complete, etc.)
        clean_task = task_text
        for prefix in ["Process ", "Complete ", "Paid ", "Send ", "File ", "Review ", "Update ", "Handle "]:
            if clean_task.startswith(prefix):
                clean_task = clean_task[len(prefix):]

        # Build intelligent summary from task + notes
        if notes_text:
            # Look for key patterns in notes
            summary = f"{clean_task}"

            # Add notes as context if it's short and meaningful
            if len(notes_text) < 40 and notes_text.lower() not in ("done", "completed", "paid", "sent"):
                summary = f"{clean_task} - {notes_text}"
            elif any(char.isdigit() for char in notes_text):
                # If notes contain numbers (amounts, dates, etc.), include them
                summary = f"{clean_task} {notes_text}"
            else:
                summary = clean_task
        else:
            summary = clean_task

        # Add property if it's specific (not generic)
        if property_val and property_val.lower() not in ("general", "n/a", "", "tps"):
            summary = f"{property_val} - {summary}"

        # Truncate if too long
        if len(summary) > 75:
            summary = summary[:72] + "..."

        items.append(f'                <li>{summary}</li>')

    return '\n'.join(items)

def inject_into_html(tasks_by_category_status, archive_items):
    """Inject generated content into index.html between markers."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Build HTML sections organized by category and status
    category_sections = {}

    for category in CATEGORY_ORDER:
        if category not in tasks_by_category_status:
            category_sections[category] = ""
            continue

        category_html = ""
        for status in STATUS_ORDER:
            tasks = tasks_by_category_status[category].get(status, [])
            if not tasks:
                continue

            # Build status subsection
            status_class_map = {
                "Stuck": "status-stuck",
                "Maya Needs Help": "status-maya-help",
                "New": "status-new",
                "In Progress": "status-in-progress",
                "FYI Only": "status-fyi",
            }
            status_class = status_class_map.get(status, "status-fyi")

            category_html += f'        <div class="status-subsection">\n'
            category_html += f'            <h4 class="status-subheader {status_class}">● {status} ({len(tasks)})</h4>\n'
            category_html += f'            <div class="tasks-list">\n'

            for idx, task in enumerate(tasks):
                item_id = f"{category.lower()}-{status.lower().replace(' ', '-')}-{idx}"
                category_html += build_task_item(task, item_id)

            category_html += f'            </div>\n'
            category_html += f'        </div>\n'

        category_sections[category] = category_html

    # Build Quick Wins
    quick_wins_html = build_quick_wins(archive_items)

    # Inject each section
    markers = {
        "QUICK_WINS": ("<!-- QUICK_WINS_START -->", "<!-- QUICK_WINS_END -->"),
        "OPERATIONS_ADMIN": ("<!-- OPERATIONS_ADMIN_START -->", "<!-- OPERATIONS_ADMIN_END -->"),
        "LEASING_MARKETING": ("<!-- LEASING_MARKETING_START -->", "<!-- LEASING_MARKETING_END -->"),
        "MAINTENANCE_REPAIRS": ("<!-- MAINTENANCE_REPAIRS_START -->", "<!-- MAINTENANCE_REPAIRS_END -->"),
        "FINANCIALS_ACCOUNTING": ("<!-- FINANCIALS_ACCOUNTING_START -->", "<!-- FINANCIALS_ACCOUNTING_END -->"),
        "TENANT_RELATIONS": ("<!-- TENANT_RELATIONS_START -->", "<!-- TENANT_RELATIONS_END -->"),
    }

    # Map category names to marker keys
    category_markers = {
        "Operations & Admin": "OPERATIONS_ADMIN",
        "Leasing & Marketing": "LEASING_MARKETING",
        "Maintenance & Repairs": "MAINTENANCE_REPAIRS",
        "Financials & Accounting": "FINANCIALS_ACCOUNTING",
        "Tenant Relations": "TENANT_RELATIONS",
    }

    for category, marker_key in category_markers.items():
        start_marker, end_marker = markers[marker_key]
        pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
        content = category_sections.get(category, "")
        replacement = f"{start_marker}\n{content}            {end_marker}"

        if re.search(pattern, html, re.DOTALL):
            html = re.sub(pattern, replacement, html, flags=re.DOTALL)
        else:
            print(f"  WARNING: {marker_key} markers not found in HTML")

    # Inject Quick Wins
    start_marker, end_marker = markers["QUICK_WINS"]
    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    replacement = f"{start_marker}\n{quick_wins_html}\n            {end_marker}"

    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    # Write updated HTML
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # Print summary
    total_count = sum(sum(len(tasks) for tasks in statuses.values())
                     for statuses in tasks_by_category_status.values())
    print(f"✓ Dashboard updated at {now}")
    for category in CATEGORY_ORDER:
        if category in tasks_by_category_status:
            cat_total = sum(len(tasks) for tasks in tasks_by_category_status[category].values())
            print(f"  {category}: {cat_total} tasks")
            for status in STATUS_ORDER:
                count = len(tasks_by_category_status[category].get(status, []))
                if count > 0:
                    print(f"    - {status}: {count}")
    print(f"  Quick Wins: {len(archive_items)}")

def main():
    print("🔄 TPS Dashboard Generator")
    print("=" * 50)

    try:
        print("Authenticating with Google Sheets...")
        client = authenticate()

        print("Reading Operations Log...")
        ops_by_cat_status = fetch_operations_log(client)
        total_ops = sum(sum(len(tasks) for tasks in statuses.values())
                       for statuses in ops_by_cat_status.values())
        print(f"  Found {total_ops} tasks across all categories")

        print("Reading 📦 Archive...")
        arc = fetch_archive(client, limit=9)
        print(f"  Found {len(arc)} archived items")

        print("Generating HTML...")
        inject_into_html(ops_by_cat_status, arc)

        print("=" * 50)
        print("✓ Done! Dashboard is fresh.")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
