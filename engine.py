"""Invoice parsing, deterministic matching and auditable Excel export."""
import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

FIELDS = ['buyer_tax', 'seller_tax', 'seller', 'serial', 'number', 'date', 'net', 'vat', 'total', 'currency', 'rate', 'kind', 'status']
HEADERS = ['STT', 'SỐ SERI', 'SỐ HĐ', 'NGÀY HĐ', 'TÊN NGƯỜI BÁN', 'MÃ SỐ THUẾ', 'TÊN HÀNG', 'TIỀN', 'VAT', 'TỶ GIÁ', 'SỐ LƯỢNG', 'ĐVT', 'Tổng Thành tiền', 'MÃ KHÁCH HÀNG']

def money(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite():
            raise ValueError('Số tiền không hữu hạn')
        return result
    except InvalidOperation:
        raise ValueError('Số tiền phải dùng dấu chấm thập phân, không có dấu phân cách hàng nghìn')

def text(node, path, default=''):
    found = node.find(path)
    return (found.text or '').strip() if found is not None else default

def parse_xml(raw):
    # Reject DTD/entities before parsing untrusted local documents.
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper() or b'\x00' in raw:
        raise ValueError('Không hỗ trợ DTD/entity hoặc XML UTF-16')
    root = ET.fromstring(raw)
    for node in root.iter():
        node.tag = node.tag.split('}')[-1]
    info = root if root.tag == 'DLHDon' else root.find('.//DLHDon')
    if info is None:
        raise ValueError('Không tìm thấy DLHDon trong XML hóa đơn')
    common, content = info.find('TTChung'), info.find('NDHDon')
    if common is None or content is None:
        raise ValueError('Thiếu TTChung hoặc NDHDon')
    invoice = dict(
        buyer=text(content, 'NMua/Ten'), buyer_tax=text(content, 'NMua/MST'), seller_tax=text(content, 'NBan/MST'),
        seller=text(content, 'NBan/Ten'), serial=text(common, 'KHHDon'), number=text(common, 'SHDon'),
        date=text(common, 'NLap'), net=text(content, 'TToan/TgTCThue'), vat=text(content, 'TToan/TgTThue'),
        total=text(content, 'TToan/TgTTTBSo'), currency=text(common, 'DVTTe', 'VND').upper(),
        rate=text(common, 'TGia'), kind='sales' if text(common, 'KHMSHDon') == '2' else 'vat', status='',
        items=[])
    for item in content.findall('DSHHDVu/HHDVu'):
        invoice['items'].append({'name':text(item, 'THHDVu'), 'quantity':text(item, 'SLuong'), 'unit':text(item, 'DVTinh'), 'price':text(item, 'DGia'), 'amount':text(item, 'ThTien')})
    validate(invoice)
    return invoice

def validate(invoice):
    for key in ['buyer_tax', 'seller_tax', 'serial', 'number', 'date', 'total']:
        if not invoice.get(key):
            raise ValueError(f'Thiếu trường {key}')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', invoice['date']):
        raise ValueError('Ngày phải có định dạng YYYY-MM-DD')
    from datetime import date
    date.fromisoformat(invoice['date'])
    for key in ['net', 'vat', 'total', 'rate']:
        money(invoice.get(key))
    invoice.setdefault('items', [])
    invoice['currency'] = invoice.get('currency') or 'VND'

def parse_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or not {'buyer_tax','seller_tax','serial','number','date','total'} <= set(reader.fieldnames):
        raise ValueError('CSV chưa đúng mẫu. Hãy tải mẫu CSV trong ứng dụng.')
    rows = []
    for index, row in enumerate(reader, 2):
        invoice = {field: (row.get(field) or '').strip() for field in FIELDS}
        try:
            validate(invoice)
        except ValueError as exc:
            raise ValueError(f'Dòng {index}: {exc}') from exc
        rows.append(invoice)
    if not rows:
        raise ValueError('CSV không có hóa đơn')
    keys = [identity(x) for x in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('CSV có khóa hóa đơn trùng. Cần kiểm tra trước khi nhập.')
    return rows

def identity(invoice):
    serial = invoice['serial'].upper().strip()
    # Cash-register notation 1K26THT and K26THT refer to the same series.
    if re.fullmatch(r'[1-6]K\w+', serial):
        serial = serial[1:]
    return (invoice['buyer_tax'].strip(), invoice['seller_tax'].strip(), serial, invoice['number'].lstrip('0') or '0')

def reconcile(cqt, documents):
    results, used = [], set()
    for source in cqt:
        matches = [(index, d) for index, d in enumerate(documents) if identity(d) == identity(source)]
        issues, doc = [], None
        if not matches:
            issues.append('CHƯA TÌM THẤY CHỨNG TỪ')
        else:
            used.update(index for index, _ in matches)
            xml = [(i,d) for i,d in matches if d.get('method','xml') == 'xml']
            preferred = xml if xml else matches
            if len(preferred) > 1:
                issues.append('TRÙNG KHÓA')
            else:
                doc = dict(preferred[0][1])
                doc['related_files'] = [{'filename':d.get('filename',''), 'fingerprint':d.get('fingerprint',''), 'method':d.get('method','xml')} for _,d in matches]
                if doc.get('needs_review'): issues.append('CHỜ XÁC NHẬN TRÍCH XUẤT')
                if xml:
                    for _,other in matches:
                        if other.get('method','xml') != 'xml' and not other.get('needs_review') and any(money(doc.get(k)) != money(other.get(k)) for k in ['net','vat','total']):
                            issues.append('CHÊNH LỆCH GIỮA XML VÀ PDF'); break
        if doc is not None:
            for field in ['net', 'vat', 'total']:
                if money(source.get(field)) != money(doc.get(field)):
                    issues.append(f'CHÊNH LỆCH TIỀN · {field}')
            if source['date'] != doc['date']:
                issues.append('CHÊNH NGÀY HÓA ĐƠN')
            if source.get('currency','VND') != doc.get('currency','VND'):
                issues.append('CHÊNH LOẠI TIỀN')
        if source.get('currency','VND') != 'VND':
            if not source.get('rate') or (doc and not doc.get('rate')):
                issues.append('THIẾU TỶ GIÁ')
            elif doc and money(source['rate']) != money(doc['rate']):
                issues.append('CHÊNH TỶ GIÁ')
        if source.get('status'):
            issues.append('HÓA ĐƠN ĐẶC BIỆT · ' + source['status'])
        results.append({'cqt':source, 'document':doc, 'issues':issues, 'state':'exception' if issues else 'matched'})
    orphans = [d for i,d in enumerate(documents) if i not in used]
    return results, orphans

def excel(company, period, results, orphans, errors):
    wb = Workbook()
    wb.remove(wb.active)
    for name in ['BangKe_MuaVao','NgoaiLe','ChiTiet_HoaDon','CQT_ChuanHoa','HoaDon_DocDuoc','Log_XuLy']:
        wb.create_sheet(name)
    main = wb['BangKe_MuaVao']; main.append(HEADERS)
    exception = wb['NgoaiLe']; exception.append(['SỐ HĐ','MST NGƯỜI BÁN','NGOẠI LỆ','FILE NGUỒN'])
    detail = wb['ChiTiet_HoaDon']; detail.append(['SỐ HĐ','MST NGƯỜI BÁN','TÊN HÀNG NGUYÊN VĂN','SỐ LƯỢNG','ĐVT','THÀNH TIỀN'])
    for index, result in enumerate(results, 1):
        src, doc = result['cqt'], result['document']
        data = doc or src
        items = data.get('items', [])
        net, vat = money(data.get('net')), money(data.get('vat'))
        if data.get('kind') == 'sales' and vat is None and net is None:
            net = money(data['total'])
        description = data.get('display_name') or '\n'.join(x['name'] for x in items)
        main.append([index, src['serial'], src['number'], src['date'], data.get('seller',''), src['seller_tax'], description, net, vat, money(data.get('rate')), '\n'.join(x['quantity'] for x in items), '\n'.join(x['unit'] for x in items), money(data['total']), ''])
        if result['issues']:
            exception.append([src['number'],src['seller_tax'],'; '.join(result['issues']), (doc or {}).get('filename','')])
            for cell in main[main.max_row]: cell.fill = PatternFill('solid', fgColor='FFF3DD')
        for item in items:
            detail.append([src['number'],src['seller_tax'],item['name'],item['quantity'],item['unit'],money(item.get('amount'))])
    for doc in orphans:
        exception.append([doc['number'],doc['seller_tax'],'KHÔNG THẤY TRÊN CQT',doc.get('filename','')])
    for err in errors:
        exception.append(['','','CÓ FILE - ĐỌC LỖI · '+err['error'],err['filename']])
    for name, records in [('CQT_ChuanHoa',[r['cqt'] for r in results]),('HoaDon_DocDuoc',[r['document'] for r in results if r['document']] + orphans)]:
        ws = wb[name]; ws.append(FIELDS + ['filename'])
        for row in records: ws.append([row.get(field,'') for field in FIELDS + ['filename']])
    wb['Log_XuLy'].append(['CÔNG TY','MST','KỲ','CQT','KHỚP','NGOẠI LỆ','NGUỒN'])
    wb['Log_XuLy'].append([company['name'],company['tax'],period,len(results),sum(not r['issues'] for r in results),sum(bool(r['issues']) for r in results),'Danh sách nhập từ CSV/Excel; chưa xác thực phiên CQT trực tiếp'])
    for ws in wb:
        ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = PatternFill('solid',fgColor='123D38'); cell.font = Font(color='FFFFFF',bold=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                # Prevent spreadsheet formula injection; retain exact textual invoice identifiers.
                if isinstance(cell.value,str): cell.data_type = 's'; cell.number_format = '@'
                elif isinstance(cell.value,(Decimal,float,int)):
                    number = Decimal(str(cell.value))
                    scale = max(0, -number.normalize().as_tuple().exponent)
                    cell.number_format = '#,##0' + ('.' + '0' * min(scale, 8) if scale else '')
                cell.alignment = Alignment(vertical='top',wrap_text=True)
                cell.border = Border(bottom=Side(style='hair',color='DDE6E2'))
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = 23
        ws.row_dimensions[1].height = 32
    main.column_dimensions['G'].width = 55
    main.column_dimensions['E'].width = 40
    for col in ['B','C','F','N']:
        for cell in main[col][1:]: cell.number_format = '@'
    for name in ['CQT_ChuanHoa','HoaDon_DocDuoc','Log_XuLy']: wb[name].sheet_state = 'hidden'
    out=io.BytesIO(); wb.save(out); return out.getvalue()
