"""Additional local workflow routes and bounded background-job tracking."""
import base64
import json
import logging
from pathlib import Path
import secrets
import threading
from urllib.parse import urlparse,parse_qs
import documents
import engine
import workspace

JOBS={}
BUSY=set()
JOB_LOCK=threading.Lock()

def extend_handler(base,context):
    connect=context['connect'];lock=context['LOCK'];company=context['company'];valid_period=context['valid_period'];report=context['report']
    def start_job(taxes,period,operation):
        with JOB_LOCK:
            if any(t in BUSY for t in taxes):raise ValueError('Công ty đang có tác vụ chạy')
            identifier=secrets.token_hex(12)
            job={'id':identifier,'state':'running','operation':operation,'company':'','file':'','counts':{},'results':[]}
            JOBS[identifier]=job;BUSY.update(taxes)
        def run():
            try:
                for tax in taxes:
                    job['company']=tax
                    try:
                        with lock,connect() as db:
                            company(db,tax)
                            def progress(counts,name):job.update(counts=counts,file=name)
                            result=workspace.scan_folder(db,tax,period,progress) if operation=='scan' else workspace.retry_errors(db,tax,period)
                            current=report(db,tax,period)
                            if current['results'] and workspace.settings(db,tax)['output_folder']:result['export']=workspace.save_output(db,tax,period,current)
                        job['results'].append({'tax':tax,'result':result})
                    except Exception as exc:
                        logging.exception('Local batch operation failed')
                        job['results'].append({'tax':tax,'error':str(exc)})
                job['state']='done'
            finally:
                with JOB_LOCK:BUSY.difference_update(taxes)
        threading.Thread(target=run,daemon=True).start()
        for key in list(JOBS):
            if len(JOBS)>100 and JOBS[key]['state']=='done':JOBS.pop(key)
        return {'id':identifier}
    class Handler(base):
        def do_GET(self):
            path=urlparse(self.path).path
            extra=['/api/backup','/api/health','/api/job','/api/settings','/api/history','/api/audit','/api/revision','/api/file','/api/candidate','/api/pdf']
            if path not in extra:return super().do_GET()
            try:
                self.guard();q=parse_qs(urlparse(self.path).query);arg=lambda key:q.get(key,[''])[0]
                if path=='/api/job':
                    if arg('id') not in JOBS:raise ValueError('Không có tác vụ này')
                    return self.send(200,JOBS[arg('id')])
                if path=='/api/health':return self.send(200,{'app':'So Mua','version':'1.0-local','ocr':bool(documents.shutil.which('tesseract')),'cqt':'not_integrated'})
                with lock,connect() as db:
                    if path=='/api/backup':
                        import sqlite3,tempfile
                        with tempfile.TemporaryDirectory() as directory:
                            backup_path=Path(directory)/'invoices.sqlite'
                            backup_db=sqlite3.connect(backup_path)
                            try:db.backup(backup_db)
                            finally:backup_db.close()
                            return self.send(200,backup_path.read_bytes(),'application/octet-stream','so-mua-backup.sqlite')
                    tax=arg('tax');company(db,tax)
                    if path=='/api/settings':return self.send(200,workspace.settings(db,tax))
                    period=valid_period(arg('period'))
                    if path=='/api/history':return self.send(200,[dict(r) for r in db.execute('SELECT id,version,time,closed FROM revisions WHERE company=? AND period=? ORDER BY version DESC',(tax,period))])
                    if path=='/api/audit':return self.send(200,[dict(r) for r in db.execute("SELECT time,event,detail FROM audit WHERE company=? AND (period=? OR period='') ORDER BY id DESC LIMIT 200",(tax,period))])
                    if path=='/api/revision':
                        row=db.execute('SELECT workbook,version FROM revisions WHERE id=? AND company=? AND period=?',(arg('id'),tax,period)).fetchone()
                        if not row:raise ValueError('Không tìm thấy phiên bản')
                        return self.send(200,row['workbook'],'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',f'bang-ke-{tax}-{period}-v{row["version"]}.xlsx')
                    row=db.execute('SELECT * FROM raw_files WHERE company=? AND fingerprint=? AND period=?',(tax,arg('fingerprint'),period)).fetchone()
                    if not row:raise ValueError('Không tìm thấy file nguồn trong công ty/kỳ này')
                    if path=='/api/file':
                        ext=Path(row['filename']).suffix.lower();ctype={'.xml':'application/xml','.pdf':'application/pdf','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png'}.get(ext,'application/octet-stream')
                        return self.send(200,row['content'],ctype,'chung-tu'+ext)
                    if path=='/api/candidate':
                        record=db.execute("SELECT body FROM documents WHERE company=? AND source='xml' AND fingerprint=?",(tax,arg('fingerprint'))).fetchone()
                        return self.send(200,{'filename':row['filename'],'record':json.loads(record['body'] if record else row['candidate'])})
                    record=json.loads(row['candidate'])
                    if record.get('method')!='xml':raise ValueError('Chỉ sinh PDF bản thể hiện từ XML')
                    return self.send(200,documents.pdf_representation(record),'application/pdf','ban-the-hien.pdf')
            except (ValueError,KeyError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})
            except Exception:
                logging.exception('GET failed');self.send(500,{'error':'Không thực hiện được yêu cầu; xem log ứng dụng'})
        def do_POST(self):
            extra=['/api/open-cqt','/api/cqt-preview','/api/settings','/api/review','/api/version','/api/reopen','/api/save-export','/api/scan','/api/retry','/api/batch']
            if self.path not in extra:return super().do_POST()
            try:
                self.guard(True);size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=24_000_000:raise ValueError('Mỗi lượt tối đa 24 MB')
                data=json.loads(self.rfile.read(size))
                if self.path in ['/api/scan','/api/retry','/api/batch']:
                    period=valid_period(data['period'])
                    if self.path=='/api/batch':
                        with lock,connect() as db:
                            taxes=[r['tax'] for r in db.execute('SELECT tax FROM companies WHERE demo=0') if workspace.settings(db,r['tax'])['enabled'] and workspace.settings(db,r['tax'])['source_folder']]
                        if not taxes:raise ValueError('Chưa có công ty bật xử lý và cấu hình thư mục')
                    else:taxes=[data['tax']]
                    return self.send(200,start_job(taxes,period,'retry' if self.path=='/api/retry' else 'scan'))
                with lock,connect() as db:
                    if data.get('tax') in BUSY:raise ValueError('Công ty đang có tác vụ chạy')
                    if self.path=='/api/cqt-preview':
                        raw=base64.b64decode(data['file']['data'],validate=True)
                        return self.send(200,documents.preview_table(raw,data['file']['name']))
                    tax=data['tax'];company(db,tax)
                    if self.path=='/api/open-cqt':result=workspace.open_cqt(tax,context['DATA'])
                    elif self.path=='/api/settings':result=workspace.save_settings(db,tax,data)
                    elif self.path=='/api/review':result=workspace.review(db,tax,valid_period(data['period']),data['fingerprint'],data['record'])
                    elif self.path=='/api/version':result=workspace.save_revision(db,tax,valid_period(data['period']),report(db,tax,data['period']),bool(data.get('closed')))
                    elif self.path=='/api/reopen':
                        period=valid_period(data['period']);db.execute('INSERT OR REPLACE INTO period_state VALUES(?,?,0)',(tax,period));workspace.audit(db,tax,period,'MỞ PHIÊN BẢN MỚI','Giữ nguyên các bản đã lưu');result={'opened':True}
                    elif self.path=='/api/save-export':
                        period=valid_period(data['period']);result=workspace.save_output(db,tax,period,report(db,tax,period))
                self.send(200,result)
            except (ValueError,KeyError,TypeError,OSError) as exc:self.send(400,{'error':str(exc)})
            except Exception:
                logging.exception('POST failed');self.send(500,{'error':'Không thực hiện được yêu cầu; xem log ứng dụng'})
    return Handler
