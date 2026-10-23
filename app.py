"""Local-first invoice assistant. Run: python app.py"""
import argparse
import base64
import hashlib
import io
import csv
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import engine
import documents
import workspace
import routes
import webbrowser

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('INVOICE_DATA_DIR', ROOT / '.data'))
LOCK = threading.RLock()

def connect():
    DATA.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(DATA/'invoices.sqlite')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''CREATE TABLE IF NOT EXISTS companies(tax TEXT PRIMARY KEY,name TEXT NOT NULL,demo INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS documents(company TEXT REFERENCES companies(tax),period TEXT,source TEXT,fingerprint TEXT,body TEXT,PRIMARY KEY(company,source,fingerprint));
    CREATE TABLE IF NOT EXISTS errors(company TEXT REFERENCES companies(tax),period TEXT,fingerprint TEXT,filename TEXT,error TEXT,PRIMARY KEY(company,fingerprint));''')
    workspace.init(db)
    return db

def company(db,tax):
    row = db.execute('SELECT * FROM companies WHERE tax=?',(tax,)).fetchone()
    if not row: raise ValueError('Chưa chọn công ty hợp lệ')
    return dict(row)

def valid_period(value):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value): raise ValueError('Kỳ không hợp lệ')
    return value

def report(db,tax,period):
    comp=company(db,tax); valid_period(period)
    sources={key:[] for key in ['cqt','xml']}
    for row in db.execute('SELECT source,body FROM documents WHERE company=? AND period=? ORDER BY rowid',(tax,period)):
        sources[row['source']].append(json.loads(row['body']))
    results,orphans=engine.reconcile(sources['cqt'],sources['xml'])
    workspace.apply_rules(db,tax,results)
    errors=[dict(row) for row in db.execute('SELECT fingerprint,filename,error FROM errors WHERE company=? AND period=?',(tax,period))]
    closed=db.execute('SELECT closed FROM period_state WHERE company=? AND period=?',(tax,period)).fetchone()
    return dict(closed=bool(closed and closed['closed']),settings=workspace.settings(db,tax),company=comp,period=period,results=results,orphans=orphans,errors=errors,stats={
        'total':len(results),'matched':sum(not r['issues'] for r in results),
        'exception':sum(bool(r['issues']) for r in results),
        'read':sum(r['document'] is not None for r in results),
        'missing':sum('CHƯA TÌM THẤY CHỨNG TỪ' in r['issues'] for r in results),
        'ambiguous':sum('TRÙNG KHÓA' in r['issues'] for r in results),
        'files':len(sources['xml']),'errors':len(errors),'orphans':len(orphans)})

def store(db,tax,period,source,fingerprint,body):
    db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?)',(tax,period,source,fingerprint,json.dumps(body,ensure_ascii=False)))

def import_files(db,payload):
    valid_period(payload['period'])
    return workspace.import_files(db,payload)

def demo(db,period):
    tax='0000000000'
    db.execute('INSERT OR IGNORE INTO companies VALUES(?,?,1)',(tax,'Công ty Minh An · dữ liệu mẫu'))
    sellers=['Công ty TNHH Thiết bị An Phát','Công ty CP Vận tải Bắc Nam','Công ty TNHH Văn phòng Xanh','Công ty TNHH Dịch vụ Hải Đăng','Công ty CP Nhiên liệu Việt']
    names=['Thiết bị giám sát hành trình GT-S7 xe 51C79096','Cước vận chuyển hàng hóa nội địa','Giấy in A4 Double A 80gsm','Dịch vụ bảo trì thiết bị văn phòng','Dầu Diesel 0,001S-V']
    for i in range(10):
        invoice={'buyer_tax':tax,'seller_tax':f'00000000{i+11:02}','seller':sellers[i%5], 'serial':'K26THT','number':f'{i+57:08}', 'date':period+f'-{i+3:02}','net':str((i+1)*1250000),'vat':str((i+1)*100000),'total':str((i+1)*1350000),'currency':'VND','rate':'','kind':'vat','status':'','items':[],'filename':'danh-sach-mau.csv'}
        store(db,tax,period,'cqt',period+str(i),invoice)
        if i<8:
            doc=dict(invoice); doc['items']=[{'name':names[i%5],'quantity':'1','unit':'Lần' if i%2 else 'Bộ','amount':invoice['net']}];doc['filename']=f'hoa-don-mau-{i+1}.xml'
            if i==7: doc['total']=str(int(doc['total'])+20000)
            store(db,tax,period,'xml',period+str(i),doc)
    return {'tax':tax}

class Handler(BaseHTTPRequestHandler):
    def send(self,status,body,ctype='application/json; charset=utf-8',filename=None):
        if isinstance(body,(dict,list)): body=json.dumps(body,ensure_ascii=False).encode()
        if isinstance(body,str):body=body.encode()
        self.send_response(status)
        self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers();self.wfile.write(body)
    def guard(self,mutation=False):
        host=self.headers.get('Host','')
        if host not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
            raise ValueError('Host không được phép')
        if mutation:
            if self.headers.get('X-Invoice-App')!='1':raise ValueError('Yêu cầu không hợp lệ')
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:raise ValueError('Origin không được phép')
    def do_GET(self):
        try:
            self.guard()
            parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query)
            if path in ['/','/app.js','/workflow.js','/style.css']:
                name={'/':'index.html','/app.js':'app.js','/workflow.js':'workflow.js','/style.css':'style.css'}[path]
                return self.send(200,(ROOT/'static'/name).read_bytes(),{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/workflow.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[path])
            with LOCK,connect() as db:
                if path=='/api/companies': return self.send(200,[dict(x) for x in db.execute('SELECT * FROM companies ORDER BY demo,name')])
                if path in ['/api/report','/api/export']:
                    result=report(db,query.get('tax',[''])[0],query.get('period',[''])[0])
                    if path=='/api/report':return self.send(200,result)
                    if not result['results']:raise ValueError('Chưa có danh sách CQT để xuất bảng kê')
                    return self.send(200,engine.excel(result['company'],result['period'],result['results'],result['orphans'],result['errors']),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',f'bang-ke-{result["company"]["tax"]}-{result["period"]}.xlsx')
                if path=='/api/template':
                    out=io.StringIO(); writer=csv.writer(out);writer.writerow(engine.FIELDS)
                    return self.send(200,'\ufeff'+out.getvalue(),'text/csv; charset=utf-8','mau-cqt.csv')
            self.send(404,{'error':'Không tìm thấy'})
        except (ValueError,KeyError) as exc:self.send(400,{'error':str(exc)})
    def do_POST(self):
        try:
            self.guard(True)
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=24_000_000:raise ValueError('Mỗi lượt nhập tối đa 20 MB')
            data=json.loads(self.rfile.read(size))
            with LOCK,connect() as db:
                if self.path=='/api/companies':
                    tax=data['tax'].strip();name=data['name'].strip()
                    if not re.fullmatch(r'\d{10}(?:-?\d{3})?',tax):raise ValueError('MST phải có 10 hoặc 13 chữ số (có thể có dấu - cho chi nhánh)')
                    if not 1<=len(name)<=200:raise ValueError('Tên công ty từ 1 đến 200 ký tự')
                    db.execute('INSERT INTO companies(tax,name) VALUES(?,?)',(tax,name)); result={'tax':tax}
                elif self.path=='/api/import': result=import_files(db,data)
                elif self.path=='/api/demo': result=demo(db,valid_period(data['period']))
                else:return self.send(404,{'error':'Không tìm thấy'})
            self.send(200,result)
        except sqlite3.IntegrityError:self.send(400,{'error':'MST đã tồn tại'})
        except (ValueError,KeyError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})

Handler=routes.extend_handler(Handler,globals())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');args=parser.parse_args()
    with connect():pass
    print(f'Trợ lý hóa đơn đang chạy tại cổng {args.port}, chỉ trên máy này.',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    if args.open:threading.Timer(.5,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
