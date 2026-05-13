#!/usr/bin/env python3
"""TPS Weekly Dashboard Update - runs every Monday 4AM UTC via GitHub Actions.
Reads Google Sheets Operations Log + Archive and updates index.html.
Operations Log columns: C=Property, D=Task, E=Notes, H=Assigned(Tricia/Maya), I=Status
Archive columns: B=Date, C=Property, D=Task, G=Assigned, H=Status, I=Notes, K=Date Completed
Requires GitHub secret: GOOGLE_CREDENTIALS (service-account JSON)
"""
import os,json,re
from datetime import datetime,timedelta
import gspread
from google.oauth2.service_account import Credentials

SHEET=os.environ.get("SPREADSHEET_ID","1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_TAB="Operations Log"; ARC_TAB="Archive"; HTML="index.html"
C_PROP,C_TASK,C_NOTE,C_ASGN,C_STAT,C_PRI,C_DATE=2,3,4,7,8,6,1
A_PROP,A_TASK,A_NOTE,A_ASGN,A_STAT,A_DATE_DONE=2,3,8,6,7,10
VALID={"tricia","trish","maya"}
DATE_FMTS=("%m/%d/%Y","%Y-%m-%d","%d/%m/%Y","%m/%d/%y","%-m/%-d/%Y","%-m/%-d/%y")

def auth():
    raw=os.environ.get("GOOGLE_CREDENTIALS")
    if not raw: raise SystemExit("Set GOOGLE_CREDENTIALS secret")
    return gspread.authorize(Credentials.from_service_account_info(
        json.loads(raw),scopes=["https://www.googleapis.com/auth/spreadsheets.readonly",
                                "https://www.googleapis.com/auth/drive.readonly"]))

def g(r,i,d=""):
    try: return str(r[i]).strip() if r[i] else d
    except: return d

def mkd(a,b): return " | ".join(x.strip() for x in [a,b] if x.strip())
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def parse_date(s):
    """Try multiple date formats, return datetime or None."""
    if not s: return None
    for fmt in DATE_FMTS:
        try: return datetime.strptime(s,fmt)
        except: pass
    return None

def get_ops(c):
    out=[]
    for r in c.open_by_key(SHEET).worksheet(OPS_TAB).get_all_values()[2:]:
        if not any(r): continue
        p=g(r,C_PROP); t=g(r,C_TASK)
        if not p and not t: continue
        if g(r,C_ASGN).lower() not in VALID: continue
        out.append({
            "p":p,"d":mkd(t,g(r,C_NOTE)),
            "a":g(r,C_ASGN),"s":g(r,C_STAT),
            "pri":g(r,C_PRI),"dt":g(r,C_DATE)
        })
    # Sort: newest Needs Approval first, then new items (newest date), then older Needs Approval, then rest
    def sort_key(x):
        s=x["s"].lower(); dt=parse_date(x["dt"])
        ts=dt.timestamp() if dt else 0
        if s=="needs approval" and ts>=(datetime.now()-timedelta(days=7)).timestamp(): return (0,-ts)
        if s!="needs approval" and ts>=(datetime.now()-timedelta(days=7)).timestamp(): return (1,-ts)
        if s=="needs approval": return (2,-ts)
        return (3,-ts)
    out.sort(key=sort_key)
    return out

def get_arc(c):
    sp=c.open_by_key(SHEET)
    try: ws=sp.worksheet(ARC_TAB)
    except: ws=sp.worksheets()[6]
    cut=datetime.now()-timedelta(days=7)
    recent=[]
    for r in ws.get_all_values()[2:]:
        if not any(r): continue
        t=g(r,A_TASK)
        if not t: continue
        # Use column K (Date Completed, index 10) as the filter date
        date_val=g(r,A_DATE_DONE)
        dt=parse_date(date_val)
        if dt and dt>=cut:
            recent.append({
                "p":g(r,A_PROP),"d":mkd(t,g(r,A_NOTE)),
                "a":g(r,A_ASGN),"s":g(r,A_STAT),"dt":date_val
            })
    # Sort by Date Completed descending (newest first)
    recent.sort(key=lambda x: parse_date(x["dt"]) or datetime.min, reverse=True)
    print(f"  Archive last-7-days items: {len(recent)}")
    for it in recent: print(f"    {it['dt']} | {it['p']} - {it['d'][:60]}")
    return recent

def card(t):
    p=esc(t["p"]); d=esc(t["d"]); a=esc(t["a"]); s=t["s"]
    ctrl=""
    if s.lower()=="needs approval":
        ctrl=(
            '\n    <div class="task-controls">'
            '\n      <div class="btn-group">'
            '\n        <button class="btn-control" onclick="setResponse(this,\'approved\')">Approved</button>'
            '\n        <button class="btn-control" onclick="setResponse(this,\'disapproved\')">Disapproved</button>'
            '\n        <button class="btn-control" onclick="setResponse(this,\'hold\')">On Hold</button>'
            '\n      </div>'
            '\n      <div class="task-note"><input type="text" placeholder="Add approval note..." onchange="updateNote(this)"></div>'
            '\n    </div>'
        )
    cls=s.lower().replace(" ","-")
    return (f'\n    <div class="task-card {cls}">'
            f'\n      <div class="task-header">'
            f'\n        <div class="task-property">{p}</div>'
            f'\n        <div class="task-meta"><span class="assignee-tag">{a}</span>'
            f' <span class="status-label">{esc(s)}</span></div>'
            f'\n      </div>'
            f'\n      <div class="task-issue">{d}</div>{ctrl}'
            f'\n    </div>')

def li(it):
    p=esc(it["p"]); d=esc(it["d"]); a=esc(it.get("a",""))
    label=f"{p} - {d}" if p and p.lower()!="general" else d
    assignee=f" ({a})" if a else ""
    return f"    <li>{label}{assignee}</li>"

def ensure_markers(h):
    if "<!-- ARCHIVE-START -->" not in h:
        h=re.sub(r'(<ul class="wins-list">)(.*?)(</ul>)',
                  r'\g<1>\n<!-- ARCHIVE-START -->\n<!-- ARCHIVE-END -->\n  \g<3>',
                  h,flags=re.DOTALL)
    if "<!-- OPS-LOG-START -->" not in h:
        h=re.sub(r'(<div class="tasks-list">)(.*?)(</div>)',
                  r'\g<1>\n<!-- OPS-LOG-START -->\n<!-- OPS-LOG-END -->\n  \g<3>',
                  h,flags=re.DOTALL,count=1)
    return h

def inject(ops,arc):
    with open(HTML,"r",encoding="utf-8") as f: html=f.read()
    html=ensure_markers(html)
    now=datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
    li_html="\n".join(li(i) for i in arc)
    html=re.sub(r"<!-- ARCHIVE-START -->.*?<!-- ARCHIVE-END -->",
                f"<!-- ARCHIVE-START -->\n<!-- updated: {now} -->\n{li_html}\n<!-- ARCHIVE-END -->",
                html,flags=re.DOTALL)
    cards="".join(card(t) for t in ops)
    html=re.sub(r"<!-- OPS-LOG-START -->.*?<!-- OPS-LOG-END -->",
                f"<!-- OPS-LOG-START -->\n<!-- updated: {now} -->\n{cards}\n<!-- OPS-LOG-END -->",
                html,flags=re.DOTALL)
    with open(HTML,"w",encoding="utf-8") as f: f.write(html)
    print(f"Done: {now} | ops={len(ops)} arc={len(arc)}")

def main():
    print("Connecting..."); c=auth()
    print("Reading ops log..."); ops=get_ops(c); print(f"  {len(ops)} tasks")
    print("Reading archive..."); arc=get_arc(c)
    inject(ops,arc)

if __name__=="__main__": main()
