#!/usr/bin/env python3
"""
Weekly Dashboard Update Script
Reads data from Google Sheets Operations Tracker and updates index.html
Runs every Monday at 4:00 AM via GitHub Actions
"""

import os
import json
import re
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_LOG_TAB    = "Operations Log"
ARCHIVE_TAB    = "Archive"
INDEX_HTML     = "index.html"

# Column indices (0-based) for Operations Log
COL_DATE       = 1   # B - date
COL_PROPERTY   = 2   # C - property address
COL_TASK       = 3   # D - task / issue
COL_NOTES      = 4   # E - notes
COL_PRIORITY   = 6   # G - priority
COL_ASSIGNED   = 7   # H - assigned to (Tricia / Maya)
COL_STATUS     = 8   # I - status

# Column indices for Archive tab
A_DATE         = 1   # B
A_PROPERTY     = 2   # C
A_TASK         = 3   # D
A_ASSIGNED     = 6   # G
A_STATUS       = 7   # H
A_NOTES        = 8   # I

VALID_ASSIGNEES = {"tricia", "trish", "maya"}
MAX_ARCHIVE_ITEMS = 6
MIN_ARCHIVE_ITEMS = 4


def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS secret is not set.")
    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def safe_get(row, idx, default=""):
    try:
        val = row[idx]
        return str(val).strip() if val is not None else default
    except IndexError:
        return default


def combine_description(task, notes):
    parts = [p.strip() for p in [task, notes] if p.strip()]
    return " | ".join(parts)


def html_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def status_class(status):
    mapping = {
        "open": "status-open",
        "in progress": "status-in-progress",
        "done": "status-done",
        "needs approval": "status-needs-approval",
    }
    return mapping.get(status.lower(), "status-open")


def priority_class(priority):
    mapping = {"high": "priority-high", "medium": "priority-medium", "low": "priority-low"}
    return mapping.get(priority.lower(), "priority-medium")


def fetch_ops_log(client):
    sheet = client.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(OPS_LOG_TAB)
    rows = ws.get_all_values()
    tasks = []
    for row in rows[2:]:
        if not any(row):
            continue
        property_addr = safe_get(row, COL_PROPERTY)
        task = safe_get(row, COL_TASK)
        notes = safe_get(row, COL_NOTES)
        assigned = safe_get(row, COL_ASSIGNED)
        status = safe_get(row, COL_STATUS)
        priority = safe_get(row, COL_PRIORITY)
        date_val = safe_get(row, COL_DATE)
        if not property_addr and not task:
            continue
        if assigned.lower() not in VALID_ASSIGNEES:
            continue
        tasks.append({
            "date": date_val, "property": property_addr,
            "desc": combine_description(task, notes),
            "assigned": assigned, "status": status, "priority": priority,
        })
    return tasks


def fetch_archive(client):
    sheet = client.open_by_key(SPREADSHEET_ID)
    # Try both tab names
    try:
        ws = sheet.worksheet(ARCHIVE_TAB)
    except Exception:
        ws = sheet.worksheets()[6]
    rows = ws.get_all_values()
    cutoff = datetime.now() - timedelta(days=7)
    items = []
    all_items = []
    for row in rows[2:]:
        if not any(row):
            continue
        task = safe_get(row, A_TASK)
        if not task:
            continue
        date_str = safe_get(row, A_DATE)
        item = {
            "date": date_str, "property": safe_get(row, A_PROPERTY),
            "desc": combine_description(task, safe_get(row, A_NOTES)),
            "assigned": safe_get(row, A_ASSIGNED), "status": safe_get(row, A_STATUS),
        }
        all_items.append(item)
        row_date = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                row_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if row_date and row_date >= cutoff:
            items.append(item)
    items.sort(key=lambda x: x["date"], reverse=True)
    if len(items) < MIN_ARCHIVE_ITEMS:
        for it in all_items:
            if it not in items:
                items.append(it)
            if len(items) >= MAX_ARCHIVE_ITEMS:
                break
    return items[:MAX_ARCHIVE_ITEMS]


def build_ops_rows(tasks):
    rows_html = []
    for t in tasks:
        approval_note = ""
        if t["status"].lower() == "needs approval":
            approval_note = ('<br><span class="approval-note">'
                            '&#9888; Action required: please review and add your approval note.</span>')
        rows_html.append(
            f'<tr>'
            f'<td class="property-cell">{html_escape(t["property"])}</td>'
            f'<td class="desc-cell">{html_escape(t["desc"])}{approval_note}</td>'
            f'<td><span class="status-badge {status_class(t["status"])}">'
            f'{html_escape(t["status"])}</span></td>'
            f'<td><span class="assignee-badge">{html_escape(t["assigned"])}</span></td>'
            f'<td><span class="priority-badge {priority_class(t["priority"])}">'
            f'{html_escape(t["priority"])}</span></td>'
            f'</tr>'
        )
    return "\n".join(rows_html)


def build_archive_rows(items):
    rows_html = []
    for it in items:
        rows_html.append(
            f'<tr>'
            f'<td class="property-cell">{html_escape(it["property"])}</td>'
            f'<td class="desc-cell">{html_escape(it["desc"])}</td>'
            f'<td>{html_escape(it["date"])}</td>'
            f'<td><span class="assignee-badge">{html_escape(it["assigned"])}</span></td>'
            f'<td><span class="status-badge status-done">{html_escape(it["status"])}</span></td>'
            f'</tr>'
        )
    return "\n".join(rows_html)


def inject_into_html(ops_rows, archive_rows):
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    updated_on = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

    ops_pattern = r'<!-- OPS-LOG-START -->[\s\S]*?<!-- OPS-LOG-END -->'
    ops_block = (f'<!-- OPS-LOG-START -->\n<!-- Auto-updated: {updated_on} -->\n'
                 f'{ops_rows}\n<!-- OPS-LOG-END -->')
    if re.search(ops_pattern, html):
        html = re.sub(ops_pattern, ops_block, html)
    else:
        print("WARNING: OPS-LOG markers not found in index.html")

    arc_pattern = r'<!-- ARCHIVE-START -->[\s\S]*?<!-- ARCHIVE-END -->'
    arc_block = (f'<!-- ARCHIVE-START -->\n<!-- Auto-updated: {updated_on} -->\n'
                 f'{archive_rows}\n<!-- ARCHIVE-END -->')
    if re.search(arc_pattern, html):
        html = re.sub(arc_pattern, arc_block, html)
    else:
        print("WARNING: ARCHIVE markers not found in index.html")

    ts_pattern = r'(id=["']last-updated["'][^>]*>)[^<]*(</)'
    html = re.sub(ts_pattern, rf'\g<1>Last updated: {updated_on}\g<2>', html)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html updated at {updated_on}")


def main():
    print("Connecting to Google Sheets...")
    client = get_sheets_client()
    print(f"Fetching Operations Log...")
    tasks = fetch_ops_log(client)
    print(f"  Found {len(tasks)} tasks (Tricia + Maya)")
    print(f"Fetching Archive (last 7 days)...")
    archive_items = fetch_archive(client)
    print(f"  Selected {len(archive_items)} completed items")
    ops_rows = build_ops_rows(tasks)
    archive_rows = build_archive_rows(archive_items)
    print("Injecting data into index.html...")
    inject_into_html(ops_rows, archive_rows)
    print("Done!")


if __name__ == "__main__":
    main()
