#!/usr/bin/env python3
"""TPS Weekly Dashboard Update - runs every Monday 4AM UTC via GitHub Actions.
Reads Google Sheets Operations Log + Archive and updates index.html.

Operations Log columns: C=Property, D=Task, E=Notes, H=Assigned(Tricia/Maya), I=Status
Archive columns: C=Property, D=Task, G=Assigned, H=Status, I=Notes

Requires GitHub secret: GOOGLE_CREDENTIALS (service-account JSON)
"""
import os,json,re
from datetime import datetime,timedelta
import gspread
from google.oauth2.service_account import Credentials

SHEET=os.environ.get("SPREADSHEET_ID","1PETs8uNdhJyLs0VibspKZk1Jts8hqQcaFcxKWneBiQ4")
OPS_TAB="Operations Log"; ARC_TAB="Archive"; HTML="index.html"
C_PROP,C_TASK,C_NOTE,C_ASGN,C_STAT,C_PRI=2,3,4,7,8,6
A_PROP,A_TASK,A_NOTE,A_ASGN,A_STAT,A_DATE=2,3,8,6,7,1
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
    try: ws=sp.worksheet(ARC_TAB)
    except: ws=sp.worksheets()[6]
    cut=datetime.now()-timedelta(days=7); recent=[]; pool=[]
    for r in ws.get_all_values()[2:]:
        if not any(r): continue
        t=g(r,A_TASK)
        if not t: continue
        it={"p":g(r,A_PROP),"d":mkd(t,g(r,A_NOTE)),"a":g(r,A_ASGN),"s":g(r,A_STAT),"dt":g(r,A_DATE)}
        pool.append(it)
        for fmt in ("%m/%d/%Y","%Y-%m-%d","%d/%m/%Y"):
            try:
                if datetime.strptime(it["dt"],fmt)>=cut: recent.append(it); break
            except: pass
    recent.sort(key=lambda x:x["dt"],reverse=True)
    if len(recent)<4:
        for x in pool:
            if x not in recent: recent.append(x)
            if len(recent)>=6: break
    return recent[:6]

def card(t):
    p=esc(t["p"]); d=esc(t["d"]); a=esc(t["a"]); s=t["s"]
    ctrl=""
    if s.lower()=="needs approval":
        ctrl=(
            '\n            <div class="task-controls">'
            '\n                <div class="btn-group">'
            '\n                    <button class="btn-control" onclick="setResponse(this,\'approved\')">Approved</button>'
            '\n                    <button class="btn-control" onclick="setResponse(this,\'disapproved\')">Disapproved</button>'
            '\n                    <button class="btn-control" onclick="setResponse(this,\'hold\')">On Hold</button>'
            '\n                </div>'
            '\n                <div class="task-note"><input type="text" placeholder="Add approval note..." onchange="updateNote(this)"></div>'
            '\n            </div>'
        )
    cls=s.lower().replace(" ","-")
    return (f'\n        <div class="task-card {cls}">'
            f'\n            <div class="task-header">'
            f'\n                <div class="task-property">{p}</div>'
            f'\n                <div class="task-meta"><span class="assignee-tag">{a}</span> <span class="status-label">{esc(s)}</span></div>'
            f'\n            </div>'
            f'\n            <div class="task-issue">{d}</div>{ctrl}'
            f'\n        </div>')

def li(it):
    p=esc(it["p"]); d=esc(it["d"])
    return f'            <li>{(p+" - "+d) if p and p.lower()!="general" else d}</li>'

def ensure_markers(h):
    if "<!-- ARCHIVE-START -->" not in h:
        h=re.sub(r'(<ul class="wins-list">)(.*?)(</ul>)',
                 r'\g<1>\n<!-- ARCHIVE-START -->\g<2><!-- ARCHIVE-END -->\n        \g<3>',
                 h,flags=re.DOTALL)
    if "<!-- OPS-LOG-START -->" not in h:
        h=re.sub(r'(<div class="tasks-list">)(.*?)(</div>)',
                 r'\g<1>\n<!-- OPS-LOG-START -->\g<2><!-- OPS-LOG-END -->\n        \g<3>',
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
    html=re.sub(r'(id=["\'\']last-updated["\'\'][^>]*>)[^<]*(</)',
                rf'\g<1>Last updated: {now}\g<2>',html)
    with open(HTML,"w",encoding="utf-8") as f: f.write(html)
    print(f"Done: {now} | ops={len(ops)} arc={len(arc)}")

def main():
    print("Connecting..."); c=auth()
    print("Reading ops log..."); ops=get_ops(c); print(f"  {len(ops)} tasks")
    print("Reading archive..."); arc=get_arc(c); print(f"  {len(arc)} items")
    inject(ops,arc)

if __name__=="__main__": main()
