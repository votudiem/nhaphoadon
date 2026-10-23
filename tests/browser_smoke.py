from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_workflow import XML,csv_bytes
import engine

import tempfile, threading
import app
from http.server import ThreadingHTTPServer
temporary=tempfile.TemporaryDirectory()
app.DATA=Path(temporary.name)
server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{server.server_port}'
out=Path(__file__).resolve().parents[1]/'artifacts';out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto(base)
    page.get_by_role('button',name='Khám phá dữ liệu mẫu').click()
    page.wait_for_function("() => document.querySelector('#m-total').textContent === '10'")
    assert page.locator('#m-matched').inner_text()=='7'
    assert page.locator('#invoice-rows tr').count()==10
    page.wait_for_timeout(500)
    page.screenshot(path=str(out/'tong-quan.png'),full_page=True)
    page.locator('[data-filter="exception"]').click()
    assert page.locator('#invoice-rows tr').count()==3
    page.locator('#invoice-rows tr').first.click()
    assert page.locator('#document-dialog').is_visible()
    assert 'CHÊNH LỆCH TIỀN' in page.locator('#document-content').inner_text()
    page.screenshot(path=str(out/'doi-chieu.png'),full_page=True)
    page.locator('#close-document').click()
    page.locator('#search').fill('does-not-exist')
    assert page.locator('#invoice-rows tr').count()==0
    page.locator('#search').fill('')
    page.locator('#new-company').click()
    page.locator('[name="name"]').fill('Công ty kiểm thử giao diện')
    page.locator('[name="tax"]').fill('0317557745')
    page.get_by_role('button',name='Tạo hồ sơ công ty').click()
    page.wait_for_function("() => document.querySelector('#company-tax').textContent.includes('0317557745')")
    page.locator('#period').fill('2026-10')
    page.locator('#period').dispatch_event('change')
    page.wait_for_timeout(150)
    page.locator('#file-cqt').set_input_files({'name':'cqt.csv','mimeType':'text/csv','buffer':csv_bytes([engine.parse_xml(XML)])})
    page.wait_for_function("() => document.querySelector('#m-total').textContent === '1'")
    page.locator('#file-xml').set_input_files({'name':'invoice.xml','mimeType':'application/xml','buffer':XML})
    page.wait_for_function("() => document.querySelector('#m-matched').textContent === '1'")
    page.locator('[data-filter="all"]').click()
    assert page.locator('#invoice-rows').inner_text().startswith('00000057')
    with page.expect_download() as download_info:page.locator('#export').click()
    download=download_info.value
    assert download.suggested_filename=='bang-ke-0317557745-2026-10.xlsx'
    download.save_as(str(out/'kiem-thu-xuat.xlsx'))
    page.reload();page.wait_for_function("() => document.querySelector('#m-matched').textContent === '1'")
    # Mobile layout: global page stays inside viewport; invoice table may scroll internally.
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'dien-thoai.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Page overflow on mobile'
    assert not errors,errors
    print('Browser PASS: demo, filters, document dialog, search, create company, CSV/XML upload, Excel download, reload persistence, mobile layout; no JS errors.')
    browser.close()

server.shutdown();server.server_close();thread.join();temporary.cleanup()
