#!/usr/bin/env python3
"""
TPS Daily Dashboard Generator (v2)
Reads Google Sheets Operations Log + Archive, generates fresh index.html
Runs daily at 7 AM EDT (11 AM UTC) via GitHub Actions
Uses dashboard-template.html with proper task-item structure and button handlers
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
TEMPLATE_HTML = "dashboard-template.html"

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

def build_task_item(task, item_id):
    """Generate HTML for a task item in dashboard-final.html structure."""
    property_val = html_escape(task.get("property", ""))
    task_text = html_escape(task.get("task", ""))
    notes_text = html_escape(task.get("notes", ""))
    status = task.get("status", "")

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

    # Build HTML for task item
    html = f'                <div class="task-item">\n'
    html += f'                    <div class="task-row">\n'
    html += f'                        <div class="task-info">\n'
    html += f'                            <button class="task-expand-btn">▼</button>\n'
    html += f'                            <div class="task-title">{task_text}</div>\n'
    if property_val:
        html += f'                            <div class="task-property">{property_val}</div>\n'
    html += f'                        </div>\n'
    html += f'                        <div class="task-status">\n'
    html += f'                            <div class="task-status-badge {status_class}">{status}</div>\n'
    html += f'                        </div>\n'
    html += f'                    </div>\n'
    html += f'                    <div class="task-expanded">\n'
    if notes_text:
        html += f'                        <div class="task-description">{notes_text}</div>\n'
    html += f'                        <div class="task-actions">\n'
    html += f'                            <div class="task-buttons">\n'

    # Generate buttons based on status
    if status == "Needs Approval":
        html += f'                                <button class="btn-outlined btn-approve" onclick="setResponse(\'{item_id}\', this, \'approved\')">Approve</button>\n'
        html += f'                                <button class="btn-outlined btn-hold" onclick="setResponse(\'{item_id}\', this, \'hold\')">Hold Off</button>\n'
        html += f'                                <button class="btn-outlined btn-reject" onclick="setResponse(\'{item_id}\', this, \'rejected\')">Rejected</button>\n'
    elif status == "New":
        html += f'                                <button class="btn-outlined btn-tricia" onclick="setResponse(\'{item_id}\', this, \'tricia\')">Tricia on it</button>\n'
        html += f'                                <button class="btn-outlined btn-maya" onclick="setResponse(\'{item_id}\', this, \'maya\')">Maya on it</button>\n'
        html += f'                                <div class="checkbox-container">\n'
        html += f'                                    <input type="checkbox" id="checkbox-{item_id}" class="task-checkbox" onchange="setResponse(\'{item_id}\', this, \'done\')">\n'
        html += f'                                    <label for="checkbox-{item_id}" class="checkbox-label">\n'
        html += f'                                        <div class="checkbox-box">\n'
        html += f'                                            <div class="checkbox-fill"></div>\n'
        html += f'                                            <div class="checkmark">\n'
        html += f'                                                <svg class="check-icon" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>\n'
        html += f'                                            </div>\n'
        html += f'                                            <div class="success-ripple"></div>\n'
        html += f'                                        </div>\n'
        html += f'                                        <span class="checkbox-text">Done</span>\n'
        html += f'                                    </label>\n'
        html += f'                                </div>\n'
    elif status == "In Progress":
        html += f'                                <div class="checkbox-container">\n'
        html += f'                                    <input type="checkbox" id="checkbox-{item_id}" class="task-checkbox" onchange="setResponse(\'{item_id}\', this, \'done\')">\n'
        html += f'                                    <label for="checkbox-{item_id}" class="checkbox-label">\n'
        html += f'                                        <div class="checkbox-box">\n'
        html += f'                                            <div class="checkbox-fill"></div>\n'
        html += f'                                            <div class="checkmark">\n'
        html += f'                                                <svg class="check-icon" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>\n'
        html += f'                                            </div>\n'
        html += f'                                            <div class="success-ripple"></div>\n'
        html += f'                                        </div>\n'
        html += f'                                        <span class="checkbox-text">Done</span>\n'
        html += f'                                    </label>\n'
        html += f'                                </div>\n'
    elif status == "FYI Only":
        html += f'                                <div class="checkbox-container">\n'
        html += f'                                    <input type="checkbox" id="checkbox-{item_id}" class="task-checkbox" onchange="setResponse(\'{item_id}\', this, \'done\')">\n'
        html += f'                                    <label for="checkbox-{item_id}" class="checkbox-label">\n'
        html += f'                                        <div class="checkbox-box">\n'
        html += f'                                            <div class="checkbox-fill"></div>\n'
        html += f'                                            <div class="checkmark">\n'
        html += f'                                                <svg class="check-icon" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>\n'
        html += f'                                            </div>\n'
        html += f'                                            <div class="success-ripple"></div>\n'
        html += f'                                        </div>\n'
        html += f'                                        <span class="checkbox-text">Done</span>\n'
        html += f'                                    </label>\n'
        html += f'                                </div>\n'
    # For "Stuck" and "Maya Needs Help", no buttons

    html += f'                            </div>\n'
    html += f'                            <div style="display: flex; flex-direction: column; gap: 8px;">\n'
    html += f'                                <textarea class="task-comment-input" onchange="updateNote(\'{item_id}\', this)"></textarea>\n'
    html += f'                            </div>\n'
    html += f'                        </div>\n'
    html += f'                    </div>\n'
    html += f'                </div>\n'

    return html

def build_quick_wins(archive_items):
    """Generate HTML for Quick Wins section from archive items."""
    if not archive_items:
        return '                <div class="empty-state">No recent completions</div>'

    items = []
    for item in archive_items:
        task_text = html_escape(item.get("task", ""))
        notes_text = html_escape(item.get("notes", "")).strip()

        # Remove common prefixes
        clean_task = task_text
        for prefix in ["Process ", "Complete ", "Paid ", "Send ", "File ", "Review ", "Update ", "Handle "]:
            if clean_task.startswith(prefix):
                clean_task = clean_task[len(prefix):]

        # Build intelligent summary
        if notes_text:
            if len(notes_text) < 40 and notes_text.lower() not in ("done", "completed", "paid", "sent"):
                summary = f"{clean_task} - {notes_text}"
            elif any(char.isdigit() for char in notes_text):
                summary = f"{clean_task} {notes_text}"
            else:
                summary = clean_task
        else:
            summary = clean_task

        # Truncate if too long
        if len(summary) > 75:
            summary = summary[:72] + "..."

        items.append(f'                <div class="win-item">\n'
                     f'                    <div class="win-check">✓</div>\n'
                     f'                    <div class="win-item-text">{summary}</div>\n'
                     f'                </div>')

    return '\n'.join(items)

def inject_into_html(tasks_by_category_status, archive_items):
    """Inject generated content into index.html between markers."""
    # Read template
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Update timestamp
    html = html.replace("<!-- LAST_UPDATED -->", now)

    # Build category sections
    category_sections = {}
    task_counter = 0

    for category in CATEGORY_ORDER:
        category_html = ""

        if category in tasks_by_category_status:
            for status in STATUS_ORDER:
                tasks = tasks_by_category_status[category].get(status, [])
                if not tasks:
                    continue

                for task in tasks:
                    item_id = f"task-{task_counter}"
                    category_html += build_task_item(task, item_id)
                    task_counter += 1

        if not category_html:
            category_html = '                <div class="empty-state">No items in this category</div>'

        category_sections[category] = category_html

    # Build Quick Wins
    quick_wins_html = build_quick_wins(archive_items)

    # Injection markers and replacements
    markers = {
        "QUICK_WINS": ("<!-- QUICK_WINS_START -->", "<!-- QUICK_WINS_END -->"),
        "OPERATIONS_ADMIN": ("<!-- OPERATIONS_ADMIN_START -->", "<!-- OPERATIONS_ADMIN_END -->"),
        "LEASING_MARKETING": ("<!-- LEASING_MARKETING_START -->", "<!-- LEASING_MARKETING_END -->"),
        "MAINTENANCE_REPAIRS": ("<!-- MAINTENANCE_REPAIRS_START -->", "<!-- MAINTENANCE_REPAIRS_END -->"),
        "FINANCIALS_ACCOUNTING": ("<!-- FINANCIALS_ACCOUNTING_START -->", "<!-- FINANCIALS_ACCOUNTING_END -->"),
        "TENANT_RELATIONS": ("<!-- TENANT_RELATIONS_START -->", "<!-- TENANT_RELATIONS_END -->"),
    }

    category_markers = {
        "Operations & Admin": "OPERATIONS_ADMIN",
        "Leasing & Marketing": "LEASING_MARKETING",
        "Maintenance & Repairs": "MAINTENANCE_REPAIRS",
        "Financials & Accounting": "FINANCIALS_ACCOUNTING",
        "Tenant Relations": "TENANT_RELATIONS",
    }

    # Inject each category
    for category, marker_key in category_markers.items():
        start_marker, end_marker = markers[marker_key]
        pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
        content = category_sections.get(category, "")
        replacement = f"{start_marker}\n{content}\n                {end_marker}"

        if re.search(pattern, html, re.DOTALL):
            html = re.sub(pattern, replacement, html, flags=re.DOTALL)
        else:
            print(f"  WARNING: {marker_key} markers not found in HTML")

    # Inject Quick Wins
    start_marker, end_marker = markers["QUICK_WINS"]
    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    replacement = f"{start_marker}\n{quick_wins_html}\n                {end_marker}"

    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    # Write updated HTML
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # Print summary
    total_count = sum(sum(len(tasks) for tasks in statuses.values())
                     for statuses in tasks_by_category_status.values())
    print(f"✓ Dashboard updated at {now}")
    print(f"  Total tasks: {total_count}")
    for category in CATEGORY_ORDER:
        if category in tasks_by_category_status:
            cat_total = sum(len(tasks) for tasks in tasks_by_category_status[category].values())
            if cat_total > 0:
                print(f"  {category}: {cat_total} tasks")
    print(f"  Quick Wins: {len(archive_items)}")

def main():
    print("🔄 TPS Dashboard Generator (v2)")
    print("=" * 50)

    try:
        print("Authenticating with Google Sheets...")
        client = authenticate()

        print("Reading Operations Log...")
        ops_by_cat_status = fetch_operations_log(client)
        total_ops = sum(sum(len(tasks) for tasks in statuses.values())
                       for statuses in ops_by_cat_status.values())
        print(f"  Found {total_ops} tasks")

        print("Reading Archive...")
        arc = fetch_archive(client, limit=9)
        print(f"  Found {len(arc)} archived items")

        print("Generating HTML...")
        inject_into_html(ops_by_cat_status, arc)

        print("=" * 50)
        print("✓ Done! Dashboard is fresh and ready.")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
