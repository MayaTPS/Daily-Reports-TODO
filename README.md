# TPS Dashboard Status Widget

Files:
- status-widget.css
- status-widget-client.js

Install
1. Add the CSS file to your repo and include in your dashboard HTML head:
   <link rel="stylesheet" href="/path/to/status-widget.css">

2. Add the JS file near the end of your dashboard page (before </body>):
   <script src="/path/to/status-widget-client.js"></script>

3. For every FYI item that should show the small widget, include a container with a stable data-id:
   <div class="report-item">
     <h4>FYI: Quick win — update docs</h4>
     <p>Short description...</p>
     <div class="fyi-item" data-id="quickwin-2026-05-13-1"></div>
   </div>

Notes on IDs
- The widget matches status by the ID string. Ensure the ID used in data-id matches the ID or first-column value in your Operations Log / Archive rows.
- If your sheet has an "ID" column, use those values. If not, the script falls back to the first column; choose stable slugs for items you want tracked.

Web App & Token
- This widget is configured to use your Apps Script Web App:
  WEB_APP_URL = https://script.google.com/macros/s/AKfycbxbNL6TKDf1z2SS9HAczKvYN1oSnY1WOEuMPa4Qv9VY76OuewyeBLvADNQiJI4wtppP/exec
  SECRET_TOKEN = TPSMAYA4321

Testing
1. Open your dashboard page and refresh.
2. Click any button (Tricia on it / Maya on it / Done) or add a note and blur the note box.
3. Verify the StatusUpdates sheet has a new row appended: Timestamp | ID | Status | Note | By | Source (Source will be "Dashboard").

Claude integration (two easy options)
- Option A (recommended, simplest): have Claude append rows directly to the StatusUpdates sheet in this order:
  Timestamp | ID | Status | Note | By | Source
  Example values to append:
  new Date(), "quickwin-2026-05-13-1", "Tricia on it", "Called vendor", "ClaudeAutomation", "Claude"

- Option B (POST): have Claude POST to the Apps Script Web App:
  POST to: <WEB_APP_URL>?action=update
  JSON body:
  {
    "id":"quickwin-2026-05-13-1",
    "status":"Tricia on it",
    "note":"Called vendor",
    "by":"Claude",
    "source":"Claude",
    "token":"TPSMAYA4321"
  }

Security notes
- SECRET_TOKEN is embedded in the client JS for convenience; this makes it visible in page source. For internal use this is usually acceptable, but if you need stronger security later we can proxy requests through a server-side endpoint to hide the token.
- StatusUpdates is append-only; no existing data in Operations Log/Archive is modified by dashboard POSTs.

If you want me to:
- Create a small PR in your repo with these files (I can if you give me repo access), or
- Paste the exact snippet for your Claude skill to append to the sheet (I can format it for Claude), or
- Change the widget labels/styles or make the buttons smaller — tell me which, and I’ll update the files.
