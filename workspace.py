"""Company configuration, local document archive, period versions and audit trail."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import engine
import documents

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')

def init(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS file_index(company TEXT,path TEXT,size INTEGER,mtime INTEGER,fingerprint TEXT,period TEXT,state TEXT,PRIMARY KEY(company,path));
    CREATE TABLE IF NOT EXISTS settings(company TEXT PRIMARY KEY REFERENCES companies(tax),body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS raw_files(company TEXT REFERENCES companies(tax),period TEXT,fingerprint TEXT,filename TEXT,content BLOB,candidate TEXT,PRIMARY KEY(company,fingerprint));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,company TEXT,period TEXT,time TEXT,event TEXT,detail TEXT);
    CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,company TEXT,period TEXT,version INTEGER,time TEXT,closed INTEGER,report TEXT,workbook BLOB,UNIQUE(company,period,version));
    CREATE TABLE IF NOT EXISTS period_state(company TEXT,period TEXT,closed INTEGER,PRIMARY KEY(company,period));''')

def settings(db,tax):
    row=db.execute('SELECT body FROM settings WHERE company=?',(tax,)).fetchone()
    base={'enabled':True,'source_folder':'','output_folder':'','rules':[]}
    if row:base.update(json.loads(row['body']))
    return base

def audit(db,tax,period,event,detail=''):
    db.execute('INSERT INTO audit(company,period,time,event,detail) VALUES(?,?,?,?,?)',(tax,period,now(),event,detail))

def editable(db,tax,period):
    row=db.execute('SELECT closed FROM period_state WHERE company=? AND period=?',(tax,period)).fetchone()
    if row and row['closed']:raise ValueError('Kỳ đã chốt. Bấm MỞ PHIÊN BẢN MỚI trước khi thay đổi dữ liệu; bản chốt cũ vẫn được giữ nguyên.')

def save_settings(db,tax,data):
    old=settings(db,tax)
    config={'enabled':bool(data.get('enabled',True)),'source_folder':str(data.get('source_folder','')).strip(),'output_folder':str(data.get('output_folder','')).strip(),'rules':[]}
    for key in ['source_folder','output_folder']:
        value=config[key]
        if value:
            path=Path(value).expanduser()
            if not path.is_absolute() or not path.is_dir():raise ValueError(f'{key}: cần thư mục tuyệt đối đã tồn tại trên máy chạy ứng dụng')
            path=path.resolve()
            if key=='source_folder' and path==Path(path.anchor):raise ValueError('Không quét toàn bộ ổ đĩa. Chọn thư mục hóa đơn của công ty.')
            config[key]=str(path)
            for row in db.execute('SELECT company,body FROM settings WHERE company<>?',(tax,)):
                other=json.loads(row['body']).get(key,'')
                if other:
                    other=Path(other).resolve()
                    if path==other or path in other.parents or other in path.parents:raise ValueError('Thư mục chồng lấn với công ty khác; cần tách kho theo MST')
    for rule in data.get('rules',[]):
        keyword=str(rule.get('keyword','')).strip();label=str(rule.get('label','')).strip()
        if not keyword or not label:continue
        if len(keyword)>100 or len(label)>200:raise ValueError('Quy tắc quá dài')
        if not rule.get('approved'):raise ValueError('Quy tắc cần được người dùng phê duyệt')
        config['rules'].append({'keyword':keyword,'label':label,'approved':True})
    db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(tax,json.dumps(config,ensure_ascii=False)))
    audit(db,tax,'','LƯU CẤU HÌNH','Đã cập nhật thư mục và quy tắc được phê duyệt')
    return config

def insert_document(db,tax,period,raw,name,retry=False):
    fingerprint=hashlib.sha256(raw).hexdigest()
    existing=db.execute("SELECT body,period FROM documents WHERE company=? AND source='xml' AND fingerprint=?",(tax,fingerprint)).fetchone()
    if existing and not retry:return 'cached'
    candidate={}
    try:
        candidate=documents.parse_document(raw,name)
        if candidate.get('buyer_tax') and candidate['buyer_tax']!=tax:
            if Path(name).suffix.lower()=='.xml':raise ValueError('SAI MST: chứng từ thuộc công ty khác')
            raise ValueError('MST trích xuất khác công ty: cần xem file và xác nhận lại')
        if candidate.get('date') and candidate['date'][:7]!=period:return 'filtered'
        engine.validate(candidate)
    except Exception as exc:
        # Extraction failure is data, not proof the original invoice is absent.
        if str(exc).startswith('SAI MST:'):raise ValueError(str(exc)) from exc
        if str(exc).startswith('DERIVED_PDF:'):return 'filtered'
        db.execute('INSERT OR REPLACE INTO raw_files VALUES(?,?,?,?,?,?)',(tax,period,fingerprint,name,raw,json.dumps(candidate,ensure_ascii=False)))
        db.execute('INSERT OR REPLACE INTO errors VALUES(?,?,?,?,?)',(tax,period,fingerprint,name,str(exc)[:1500]))
        return 'failed'
    candidate.update(filename=name,fingerprint=fingerprint)
    db.execute('INSERT OR REPLACE INTO raw_files VALUES(?,?,?,?,?,?)',(tax,period,fingerprint,name,raw,json.dumps(candidate,ensure_ascii=False)))
    if Path(name).suffix.lower()=='.xml':candidate['xml']=raw.decode('utf-8-sig')
    db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?)',(tax,period,'xml',fingerprint,json.dumps(candidate,ensure_ascii=False)))
    db.execute('DELETE FROM errors WHERE company=? AND fingerprint=?',(tax,fingerprint))
    return 'added'

def scan_folder(db,tax,period,progress=None):
    editable(db,tax,period)
    config=settings(db,tax);folder=config['source_folder']
    if not folder:raise ValueError('Chưa cấu hình thư mục chứng từ')
    root=Path(folder).resolve()
    if not root.is_dir():raise ValueError('Thư mục chứng từ không còn tồn tại')
    counts={x:0 for x in ['added','cached','failed','filtered','rejected','pdfs']};counts['details']=[]
    count=0
    import os
    def walk_error(exc):raise ValueError('Không thể đọc hết kho chứng từ: '+str(exc))
    for current,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d.upper()!='_PDF_CQT' and not (Path(current)/d).is_symlink()]
        for name in sorted(files):
            path=Path(current)/name
            if path.suffix.lower() not in documents.EXTENSIONS or path.is_symlink():continue
            count+=1
            if count>10000:raise ValueError('Kho vượt 10.000 file; chia nhỏ thư mục trước khi quét')
            try:
                if path.stat().st_size>15_000_000:raise ValueError('File vượt 15 MB')
                relative=str(path.relative_to(root));stat=path.stat()
                old=db.execute('SELECT * FROM file_index WHERE company=? AND path=?',(tax,str(path.resolve()))).fetchone()
                if old and old['size']==stat.st_size and old['mtime']==stat.st_mtime_ns and old['period']==period:
                    state='filtered' if old['state']=='filtered' else 'cached';fingerprint=old['fingerprint']
                else:
                    raw=path.read_bytes();fingerprint=hashlib.sha256(raw).hexdigest()
                    state=insert_document(db,tax,period,raw,relative)
                    if old and old['fingerprint']!=fingerprint:
                        references=db.execute('SELECT COUNT(*) FROM file_index WHERE company=? AND fingerprint=? AND path<>?',(tax,old['fingerprint'],str(path.resolve()))).fetchone()[0]
                        if not references:
                            db.execute("DELETE FROM documents WHERE company=? AND source='xml' AND fingerprint=?",(tax,old['fingerprint']))
                            db.execute('DELETE FROM errors WHERE company=? AND fingerprint=?',(tax,old['fingerprint']))
                        audit(db,tax,period,'FILE THAY ĐỔI',relative)
                    db.execute('INSERT OR REPLACE INTO file_index VALUES(?,?,?,?,?,?,?)',(tax,str(path.resolve()),stat.st_size,stat.st_mtime_ns,fingerprint,period,state))
                counts[state]+=1
                db.commit()
                if state in ['added','cached'] and path.suffix.lower()=='.xml' and config['output_folder']:
                    record=db.execute("SELECT body FROM documents WHERE company=? AND source='xml' AND fingerprint=?",(tax,fingerprint)).fetchone()
                    if record:
                        pdf_folder=Path(config['output_folder'])/'_PDF_CQT';pdf_folder.mkdir(exist_ok=True)
                        pdf_path=pdf_folder/(tax+'-'+fingerprint[:20]+'.pdf')
                        if not pdf_path.exists():
                            try:
                                with pdf_path.open('xb') as output:output.write(documents.pdf_representation(json.loads(record['body'])))
                                counts['pdfs']+=1
                            except FileExistsError:pass
                db.commit()
                if progress:progress(dict(counts),str(path.relative_to(root)))
            except (ValueError,OSError) as exc:
                counts['rejected']+=1;counts['details'].append({'filename':name,'error':str(exc)})
    audit(db,tax,period,'QUÉT KHO',json.dumps(counts,ensure_ascii=False))
    return counts

def retry_errors(db,tax,period):
    editable(db,tax,period)
    rows=db.execute('SELECT r.* FROM raw_files r JOIN errors e ON r.company=e.company AND r.fingerprint=e.fingerprint WHERE e.company=? AND e.period=?',(tax,period)).fetchall()
    counts={x:0 for x in ['added','cached','failed','filtered','rejected']}
    for row in rows:
        try:counts[insert_document(db,tax,period,row['content'],row['filename'],retry=True)]+=1
        except ValueError:counts['rejected']+=1
        db.commit()
    audit(db,tax,period,'XỬ LÝ LẠI FILE LỖI',json.dumps(counts))
    return counts

def review(db,tax,period,fingerprint,record):
    editable(db,tax,period)
    row=db.execute('SELECT * FROM raw_files WHERE company=? AND fingerprint=? AND period=?',(tax,fingerprint,period)).fetchone()
    if not row:raise ValueError('Không có file nguồn trong công ty/kỳ này')
    old=json.loads(row['candidate'])
    if Path(row['filename']).suffix.lower()=='.xml':raise ValueError('Không sửa dữ liệu XML gốc. Hãy kiểm tra lại chứng từ.')
    clean={k:str(record.get(k,'')).strip() for k in engine.FIELDS}
    clean['items']=[{k:str(item.get(k,'')).strip() for k in ['name','quantity','unit','price','amount']} for item in record.get('items',[])]
    engine.validate(clean)
    if clean['buyer_tax']!=tax or clean['date'][:7]!=period:raise ValueError('MST hoặc kỳ trên chứng từ không đúng công ty/kỳ đang chọn')
    if not clean['seller'] or not clean['items'] or any(not i['name'] for i in clean['items']):raise ValueError('Cần tên người bán và tên hàng nguyên văn từ chứng từ')
    for item in clean['items']:engine.money(item['amount']);engine.money(item['price'])
    clean.update(filename=row['filename'],fingerprint=fingerprint,method=old.get('method','manual'),needs_review=False,extracted_text=old.get('extracted_text',''),reviewed_at=now())
    db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?)',(tax,period,'xml',fingerprint,json.dumps(clean,ensure_ascii=False)))
    db.execute('DELETE FROM errors WHERE company=? AND fingerprint=?',(tax,fingerprint))
    audit(db,tax,period,'XÁC NHẬN TRÍCH XUẤT',json.dumps({'file':row['filename'],'before':{k:old.get(k) for k in engine.FIELDS},'after':{k:clean.get(k) for k in engine.FIELDS}},ensure_ascii=False))
    return {'saved':True}

def apply_rules(db,tax,results):
    rules=settings(db,tax)['rules']
    for result in results:
        doc=result['document']
        if not doc:continue
        names='\n'.join(i['name'] for i in doc.get('items',[]))
        hits=[r for r in rules if documents.fold(r['keyword']) in documents.fold(names)]
        labels=set(r['label'] for r in hits)
        if len(labels)==1:doc['display_name']=hits[0]['label']
        elif len(labels)>1:
            result['issues'].append('NHIỀU QUY TẮC KẾ TOÁN CÙNG ÁP DỤNG');result['state']='exception'

def save_revision(db,tax,period,result,closed=False):
    editable(db,tax,period)
    if not result['results']:raise ValueError('Chưa có danh sách CQT để lưu phiên bản')
    if closed and (result['stats']['exception'] or result['stats']['errors'] or result['stats']['orphans']):raise ValueError('Còn ngoại lệ hoặc file lỗi; hãy giải quyết trước khi chốt kỳ')
    version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM revisions WHERE company=? AND period=?',(tax,period)).fetchone()[0]
    content=engine.excel(result['company'],period,result['results'],result['orphans'],result['errors'])
    row=db.execute('INSERT INTO revisions(company,period,version,time,closed,report,workbook) VALUES(?,?,?,?,?,?,?)',(tax,period,version,now(),int(closed),json.dumps(result,ensure_ascii=False),content))
    if closed:db.execute('INSERT OR REPLACE INTO period_state VALUES(?,?,1)',(tax,period))
    audit(db,tax,period,'CHỐT KỲ' if closed else 'LƯU PHIÊN BẢN',f'v{version}')
    return {'id':row.lastrowid,'version':version,'closed':closed}

def import_files(db,payload):
    import base64
    tax,period,source=payload['tax'],payload['period'],payload['source']
    if not db.execute('SELECT 1 FROM companies WHERE tax=?',(tax,)).fetchone():raise ValueError('Chưa chọn công ty hợp lệ')
    editable(db,tax,period)
    if source not in ['cqt','xml']:raise ValueError('Nguồn nhập không hợp lệ')
    files=payload.get('files',[])
    if not 1<=len(files)<=100:raise ValueError('Mỗi lượt từ 1 đến 100 file')
    if source=='cqt' and len(files)!=1:raise ValueError('Mỗi lần nhập một danh sách CQT')
    counts={key:0 for key in ['added','cached','failed','filtered']}
    for file in files:
        name=Path(file['name'].replace('\\','/')).name
        raw=base64.b64decode(file['data'],validate=True)
        if len(raw)>15_000_000:raise ValueError('Mỗi file tối đa 15 MB')
        if source=='cqt':
            records,filtered=documents.parse_table(raw,name,tax,period,payload.get('mapping'),payload.get('header_row'),payload.get('confirm_buyer',False))
            db.execute("DELETE FROM documents WHERE company=? AND period=? AND source='cqt'",(tax,period))
            for record in records:
                record['filename']=name
                fingerprint=hashlib.sha256((period+json.dumps(engine.identity(record))).encode()).hexdigest()
                db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?)',(tax,period,'cqt',fingerprint,json.dumps(record,ensure_ascii=False)))
            counts['added']=len(records);counts['filtered']=filtered
        else:
            if Path(name).suffix.lower() not in documents.EXTENSIONS:raise ValueError('Chỉ nhận XML/PDF/JPG/JPEG/PNG')
            counts[insert_document(db,tax,period,raw,name)]+=1
    audit(db,tax,period,'NHẬP '+source.upper(),json.dumps(counts))
    return counts

def open_cqt(tax,data_root):
    """Open official site in an isolated Chrome profile; never infer login identity."""
    import os,shutil,subprocess
    if os.name!='nt' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Máy này không có màn hình desktop. Chạy app trên Windows của kế toán để mở Chrome.')
    candidates=[shutil.which('google-chrome'),shutil.which('chrome'),shutil.which('chromium')]
    if os.name=='nt':
        for key in ['PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA']:
            base=os.environ.get(key)
            if base:candidates.append(str(Path(base)/'Google/Chrome/Application/chrome.exe'))
    executable=next((p for p in candidates if p and Path(p).is_file()),None)
    if not executable:raise ValueError('Chưa tìm thấy Google Chrome. Cài Chrome để mở CQT theo hồ sơ riêng.')
    profile=Path(data_root)/'browser_profiles'/tax
    profile.mkdir(parents=True,exist_ok=True,mode=0o700)
    default=profile/'Default';default.mkdir(exist_ok=True)
    preferences=default/'Preferences'
    if not preferences.exists():preferences.write_text(json.dumps({'credentials_enable_service':False,'profile':{'password_manager_enabled':False}}),encoding='utf-8')
    subprocess.Popen([executable,'--user-data-dir='+str(profile.resolve()),'--no-first-run','--no-default-browser-check','--new-window','https://hoadondientu.gdt.gov.vn/'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return {'opened':True,'session':'unverified','message':'Đã gửi yêu cầu mở Chrome riêng. Bạn tự đăng nhập trên trang CQT; app chưa kiểm tra phiên hoặc tải dữ liệu tự động.'}


def save_output(db,tax,period,result):
    folder=settings(db,tax)['output_folder']
    if not folder:raise ValueError('Chưa cấu hình thư mục xuất Excel')
    version=save_revision(db,tax,period,result)
    row=db.execute('SELECT workbook FROM revisions WHERE id=?',(version['id'],)).fetchone()
    target=Path(folder)/f'bang-ke-{tax}-{period}-v{version["version"]}.xlsx'
    created=False
    try:
        with target.open('xb') as output:
            created=True;output.write(row['workbook'])
    except OSError:
        if created:target.unlink(missing_ok=True)
        raise
    version['filename']=str(target)
    return version
