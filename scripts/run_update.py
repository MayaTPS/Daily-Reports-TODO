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
C_PROP,C_TASK,C_NOTE,C_ASGN,C_STAT,C_PRI=2,3,4,7,8,6
A_PROP,A_TASK,A_NOTE,A_ASGN,A_STAT,A_DATE,A_DATE_DONE=2,3,8,6,7,1,10
VALID={"tricia","trish","maya"}

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

def get_ops(c):
    out=[]
    for r in c.open_by_key(SHEET).worksheet(OPS_TAB).get_all_values()[2:]:
        if not any(r): continue
        p=g(r,C_PROP); t=g(r,C_TASK)
        if not p and not t: continue
        if g(r,C_ASGN).lower() not in VALID: continue
        out.append({"p":p,"d":mkd(t,g(r,C_NOTE)),"a":g(r,C_ASGN),"s":g(r,C_STAT),"pri":g(r,C_PRI)})
    return out

def get_arc(c):
    sp=c.open_by_key(SHEET)
    # Archive tab: rows 23-30 in spreadsheet = indices 20-27 in all_rows after [2:] slice
    try: ws=sp.worksheet(ARC_TAB)
    except: ws=sp.worksheets()[6]
    all_rows=ws.get_all_values()[2:]
    cut=datetime.now()-timedelta(days=7)
    recent=[]; pool=[]
    for idx,r in enumerate(all_rows):
        if not any(r): continue
        t=g(r,A_TASK)
        if not t: continue
        date_val=g(r,A_DATE_DONE) or g(r,A_DATE)
        it={"p":g(r,A_PROP),"d":mkd(t,g(r,A_NOTE)),"a":g(r,A_ASGN),"s":g(r,A_STAT),"dt":date_val}
        pool.append(it)
        if 20<=idx<=27:
            recent.append(it)
            continue
        if date_val:
            for fmt in ("%m/%d/%Y","%Y-%m-%d","%d/%m/%Y","%m/%d/%y"):
                try:
                    if datetime.strptime(date_val,fmt)>=cut:
                        if it not in recent: recent.append(it)
                    break
                except: pass
    try:
        ops_rows=sp.worksheet(OPS_TAB).get_all_values()[2:]
        for r in ops_rows:
            if not any(r): continue
            t=g(r,C_TASK)
            if not t: continue
            if g(r,C_STAT).lower()!="done": continue
            if g(r,C_ASGN).lower() not in VALID: continue
            it={"p":g(r,C_PROP),"d":mkd(t,g(r,C_NOTE)),"a":g(r,C_ASGN),"s":"Done","dt":g(r,1)}
            if it not in recent: recent.append(it)
    except Exception as e:
        print(f"Warning: could not read Done items from Ops Log: {e}")
    seen=set(); deduped=[]
    for it in recent:
        key=(it["p"],it["d"])
        if key not in seen: seen.add(key); deduped.append(it)
    if len(deduped)<4:
        for x in pool:
            key=(x["p"],x["d"])
            if key not in seen: seen.add(key); deduped.append(x)
            if len(deduped)>=8: break
    return deduped[:8]

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
    print("Reading archive..."); arc=get_arc(c); print(f"  {len(arc)} items")
    inject(ops,arc)

if __name__=="__main__": main()
