"""Functional browser checks for mapping, review, folders and period versions."""
from pathlib import Path
import io
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
from http.server import ThreadingHTTPServer
from openpyxl import Workbook
import app
from test_workflow import XML
from test_extended import text_pdf

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);app.DATA=root/'data';source=root/'source';source.mkdir();output=root/'output';output.mkdir();(source/'invoice.xml').write_bytes(XML)
    server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    artifacts=Path(__file__).resolve().parents[1]/'artifacts';artifacts.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#new-company').click();page.locator('[name="name"]').fill('Công ty kiểm thử quy trình');page.locator('[name="tax"]').fill('0317557745');page.get_by_role('button',name='Tạo hồ sơ công ty').click();page.wait_for_function("() => document.querySelector('#company-tax').textContent.includes('0317557745')")
            page.locator('#period').fill('2026-10');page.locator('#period').dispatch_event('change');page.wait_for_timeout(100)
            wb=Workbook();ws=wb.active;ws.append(['MST người bán','Tên người bán','Ký hiệu hóa đơn','Số hóa đơn','Ngày lập','Tổng tiền chưa thuế','Tổng tiền thuế','Tổng tiền thanh toán']);ws.append(['0311111111','Công ty An Phát','K26THT','00000057','03/10/2026',1000000,80000,1080000]);out=io.BytesIO();wb.save(out)
            page.locator('#file-cqt').set_input_files({'name':'cqt.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':out.getvalue()})
            page.wait_for_selector('#mapping-dialog[open]');page.locator('[name="confirm_buyer"]').check();page.get_by_role('button',name='Nhập & đối chiếu',exact=True).click();page.wait_for_function("() => document.querySelector('#m-total').textContent==='1'")
            page.locator('#file-xml').set_input_files({'name':'invoice.pdf','mimeType':'application/pdf','buffer':text_pdf()});page.wait_for_function("() => document.querySelector('#q-files').textContent.includes('1 chứng từ')")
            page.locator('#invoice-rows tr').first.click();page.locator('#review-document').click();page.wait_for_selector('#review-dialog[open]')
            page.locator('#review-form [name="items"]').fill('Thiết bị giám sát hành trình GT-S7 | 2 | Bộ | 500000 | 1000000');page.locator('#review-form input[type="checkbox"]').check();page.get_by_role('button',name='Xác nhận & đối chiếu lại').click();page.wait_for_function("() => document.querySelector('#m-matched').textContent==='1'")
            page.locator('#settings-button').click();page.wait_for_selector('#settings-dialog[open]');page.locator('[name="source_folder"]').fill(str(source));page.locator('[name="output_folder"]').fill(str(output));page.locator('#add-rule').click();page.locator('.rule-keyword').fill('thiết bị');page.locator('.rule-label').fill('Chi phí thiết bị');page.locator('[name="approve_rules"]').check();page.get_by_role('button',name='Lưu cấu hình',exact=True).click();page.wait_for_selector('#settings-dialog',state='hidden')
            page.locator('#scan-button').click();page.wait_for_selector('#job-progress',state='visible');page.wait_for_selector('#job-progress',state='hidden');page.wait_for_function("() => document.querySelector('#q-files').textContent.includes('2 chứng từ')")
            assert list((output/'_PDF_CQT').glob('*.pdf')),'Automatic XML PDF missing';assert list(output.glob('*.xlsx')),'Automatic Excel missing'
            page.locator('#invoice-rows tr').first.click();assert page.locator('.file-links a').count()==3
            with page.expect_download() as pdf:page.get_by_role('link',name='↓ PDF bản thể hiện',exact=True).click()
            assert pdf.value.suggested_filename=='ban-the-hien.pdf';page.locator('#close-document').click()
            page.locator('#history-button').click();page.wait_for_selector('#history-dialog[open]');page.locator('#close-period').click();page.wait_for_function("() => document.querySelector('#period-state').textContent==='Đã chốt kỳ'")
            page.locator('#history-button').click();page.wait_for_selector('#history-dialog[open]');page.locator('#reopen-period').click();page.wait_for_function("() => document.querySelector('#period-state').textContent==='Kỳ đang mở'")
            page.locator('#file-xml').set_input_files({'name':'broken.xml','mimeType':'application/xml','buffer':b'<broken>'});page.wait_for_selector('#additional',state='visible');page.locator('#retry-button').click();page.wait_for_selector('#job-progress',state='visible');page.wait_for_selector('#job-progress',state='hidden');assert 'broken.xml' in page.locator('#additional-list').inner_text()
            page.locator('#history-button').click();page.wait_for_selector('#history-dialog[open]')
            with page.expect_download() as backup:page.get_by_role('link',name='↓ Sao lưu cơ sở dữ liệu toàn bộ công ty').click()
            assert backup.value.suggested_filename=='so-mua-backup.sqlite';page.locator('#history-dialog .close').click()
            page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(200)
            page.screenshot(path=str(artifacts/'quy-trinh-hoan-chinh.png'),full_page=True)
            assert not errors,errors
            print('Extended browser PASS: XLSX mapping, buyer confirmation, PDF extraction/review, company folders/rules, scan progress, automatic PDF/Excel, period close/reopen, failed-only retry, database backup; no JS errors.')
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
