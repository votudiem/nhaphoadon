'use strict';
const $ = s => document.querySelector(s);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHTML;
const format = value => value === '' || value == null ? '—' : new Intl.NumberFormat('vi-VN',{maximumFractionDigits:4}).format(Number(value));
const state = {tax:localStorage.getItem('somua-company') || '', period:localStorage.getItem('somua-period') || new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Bangkok'}).slice(0,7), companies:[], report:null, filter:'all', busy:false, view:'overview'};
let toastTimer;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Invoice-App':'1'},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok)throw new Error(result.error || 'Không thực hiện được yêu cầu');return result;}
function setBusy(value){state.busy=value;['#import-cqt','#import-xml','#demo-button','#empty-demo','#export','#period'].forEach(s=>$(s).disabled=value || (['#import-cqt','#import-xml','#export'].includes(s)&&!state.tax));$('#export').disabled=value || !state.report?.results.length;if(typeof renderWorkflow==='function')renderWorkflow();}
async function action(fn){if(state.busy)return;setBusy(true);try{await fn();}catch(error){toast(error.message,true);}finally{setBusy(false);}}
function renderCompanies(){
 $('#company-list').innerHTML=state.companies.map(c=>`<button class="company-nav ${c.tax===state.tax?'selected':''}" data-tax="${e(c.tax)}"><span class="company-monogram">${c.demo?'MẪU':'DN'}</span><div>${e(c.name)}<small>MST ${e(c.tax)}</small></div></button>`).join('');
 document.querySelectorAll('[data-tax]').forEach(button=>button.addEventListener('click',()=>action(async()=>{state.tax=button.dataset.tax;localStorage.setItem('somua-company',state.tax);renderCompanies();await refresh();})));
 const comp=state.companies.find(c=>c.tax===state.tax);
 $('#company-name').textContent=comp?.name || 'Chưa có doanh nghiệp';$('#company-tax').textContent=comp?`MST ${comp.tax} · Kho dữ liệu độc lập`:'Thêm công ty để bắt đầu quản lý hóa đơn';
 $('#company-mode').textContent=comp?.demo?'Dữ liệu mẫu · không phải hóa đơn thật':'Chế độ nhập file';
}
async function loadCompanies(){state.companies=await api('/api/companies');if(!state.companies.some(c=>c.tax===state.tax))state.tax=state.companies[0]?.tax||'';renderCompanies();}
async function refresh(){
 const tax=state.tax,period=state.period;
 state.report=null; render();
 state.report=tax?await api(`/api/report?tax=${encodeURIComponent(tax)}&period=${period}`):null;
 render();
}
function render(){
 const r=state.report; const s=r?.stats || {total:0,matched:0,exception:0,read:0,missing:0,ambiguous:0,files:0,errors:0,orphans:0};
 ['total','matched','exception'].forEach(k=>$(`#m-${k}`).textContent=s[k]);
 const totals={};(r?.results||[]).forEach(row=>{const c=row.cqt.currency||'VND';totals[c]=(totals[c]||0)+Number(row.cqt.total);});
 const currencies=Object.keys(totals);
 $('#m-money').textContent=currencies.length>1?`${currencies.length} loại tiền`:format(totals[currencies[0]]||0)+(currencies[0]==='VND'||!currencies.length?' ₫':` ${currencies[0]}`);
 $('#money-caption').textContent=currencies.length>1?'Xem từng nguyên tệ trong chứng từ':'Theo danh sách CQT · '+(currencies[0]||'VND');
 $('#side-count').textContent=s.exception+s.errors+s.orphans;
 $('#q-read').textContent=s.read;$('#q-ambiguous').textContent=s.ambiguous;$('#q-missing').textContent=s.missing;
 $('#q-files').textContent=`${s.files} chứng từ trong kho · ${s.errors} file đọc lỗi`;
 $('#quality-good').style.width=`${s.total?s.read/s.total*100:0}%`;$('#quality-ambiguous').style.width=`${s.total?s.ambiguous/s.total*100:0}%`;$('#quality-missing').style.width=`${s.total?s.missing/s.total*100:0}%`;
 $('#quality-caption').textContent=s.total?`${s.total} hóa đơn = ${s.read} có chứng từ ghép duy nhất + ${s.ambiguous} trùng khóa + ${s.missing} chưa có chứng từ.`:'Chưa có danh sách CQT trong kỳ. Nhập CSV để bắt đầu đối chiếu.';
 const clean=s.total&&!s.exception&&!s.errors&&!s.orphans;
 $('#quality-badge').textContent=clean?'Khớp các trường đã kiểm tra':s.total?'Cần kiểm tra ngoại lệ':'Chưa có dữ liệu';$('#quality-badge').className='badge '+(clean?'success':s.total?'warning':'neutral');
 $('#tab-all').textContent=s.total;$('#tab-matched').textContent=s.matched;$('#tab-exception').textContent=s.exception;
 renderRows();
 const extra=[...(r?.errors||[]).map(x=>({fingerprint:x.fingerprint,title:x.filename,issue:'CÓ FILE - ĐỌC LỖI · '+x.error})),...(r?.orphans||[]).map(x=>({fingerprint:x.fingerprint,title:`${x.number} · ${x.filename}`,issue:'KHÔNG THẤY TRÊN CQT'}))];
 $('#additional').hidden=!extra.length;$('#additional-list').innerHTML=extra.map(x=>`<div class="additional-row"><strong>${e(x.title)}</strong> — ${e(x.issue)} ${x.fingerprint?`<button class="button secondary" data-review="${e(x.fingerprint)}">Xem & kiểm tra</button>`:''}</div>`).join('');
 setBusy(state.busy);
 if(typeof renderWorkflow==='function')renderWorkflow();
}
function renderRows(){
 const all=state.report?.results||[];const search=$('#search').value.toLocaleLowerCase('vi');
 const rows=all.map((row,index)=>({...row,index})).filter(row=>(state.filter==='all'||row.state===state.filter)&&`${row.cqt.number} ${row.cqt.seller} ${row.cqt.seller_tax}`.toLocaleLowerCase('vi').includes(search));
 $('#table-count').textContent=all.length;
 $('#invoice-rows').innerHTML=rows.map(row=>`<tr class="invoice-row" data-index="${row.index}" tabindex="0" aria-label="Xem hóa đơn ${e(row.cqt.number)}"><td><strong>${e(row.cqt.number)}</strong><small>${e(row.cqt.serial)}</small></td><td><strong>${e(row.cqt.seller)}</strong><small>MST ${e(row.cqt.seller_tax)}</small></td><td>${e(row.cqt.date.split('-').reverse().join('/'))}</td><td class="right"><strong>${format(row.cqt.total)}</strong><small>${e(row.cqt.currency)}</small></td><td><span class="badge ${row.state==='matched'?'success':'warning'}">${row.state==='matched'?'✓ Đã khớp':row.issues.includes('CHƯA TÌM THẤY CHỨNG TỪ')?'◇ Chưa có chứng từ':'◇ Cần kiểm tra'}</span></td><td class="row-arrow">↗</td></tr>`).join('');
 $('#empty-state').hidden=Boolean(rows.length);$('#empty-state h3').textContent=all.length?'Không tìm thấy hóa đơn phù hợp':'Một kỳ kế toán gọn gàng bắt đầu từ đây';$('#empty-state p').hidden=Boolean(all.length);$('#empty-demo').hidden=Boolean(all.length);
 $('#result-count').textContent=`Hiển thị ${rows.length} / ${all.length} hóa đơn`;
 document.querySelectorAll('[data-index]').forEach(row=>{row.addEventListener('click',()=>openDocument(Number(row.dataset.index)));row.addEventListener('keydown',ev=>{if(ev.key==='Enter')openDocument(Number(row.dataset.index));});});
}
function openDocument(index){
 const row=state.report.results[index];const fields=[['number','Số hóa đơn'],['serial','Ký hiệu'],['date','Ngày hóa đơn'],['seller','Người bán'],['seller_tax','MST người bán'],['buyer_tax','MST người mua'],['net','Tiền trước thuế'],['vat','VAT'],['total','Tổng thanh toán'],['currency','Đơn vị tiền tệ'],['rate','Tỷ giá']];
 const panel=(title,data)=>`<section><h3>${title}</h3>${data?fields.map(([key,label])=>`<div class="field"><span>${label}</span><b>${e(['net','vat','total','rate'].includes(key)?format(data[key]):data[key]||'—')}</b></div>`).join(''):'<p>Chưa có chứng từ ghép duy nhất. Kiểm tra kho chứng từ và ngoại lệ.</p>'}</section>`;
 $('#document-content').innerHTML=`<div class="dialog-heading"><div><div class="eyebrow">TRUNG TÂM CHỨNG TỪ</div><h2>Hóa đơn ${e(row.cqt.number)}</h2></div><button class="close" id="close-document" aria-label="Đóng">×</button></div><div class="document-meta">${e(state.report.company.name)} · Kỳ ${e(state.period)}${state.report.company.demo?' · DỮ LIỆU MẪU':''}</div><div class="comparison">${panel('Danh sách CQT đã nhập',row.cqt)}${panel('Dữ liệu từ chứng từ',row.document)}</div><div class="issue-list">${row.issues.length?row.issues.map(e).join('<br>'):'✓ Khớp định danh, ngày, tiền và tỷ giá trong phạm vi kiểm tra. Chưa xác minh chữ ký số hoặc tính hợp lệ thuế.'}</div><div class="items"><strong>Hàng hóa / dịch vụ nguyên văn</strong>${(row.document?.items||[]).map(x=>`<p>${e(x.name)} · ${e(x.quantity)} ${e(x.unit)}</p>`).join('')||'<p>Chưa có chi tiết mặt hàng.</p>'}</div><div class="document-file">File nguồn: ${e(row.document?.filename||'Chưa xác định')}<br>Nguồn danh sách: ${e(row.cqt.filename)}</div>${row.document?.xml?'<div class="document-actions"><button class="button secondary" id="download-xml">↓ Tải XML nguồn</button></div>':''}`;
 $('#close-document').addEventListener('click',()=>$('#document-dialog').close());
 if(row.document?.xml)$('#download-xml').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([row.document.xml],{type:'application/xml'}));const a=document.createElement('a');a.href=url;a.download=row.document.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 if(typeof documentActions==='function')documentActions(row);
 $('#document-dialog').showModal();
}
function openCompany(){$('#company-error').textContent='';$('#company-dialog').showModal();}
$('#add-company').addEventListener('click',openCompany);$('#new-company').addEventListener('click',openCompany);$('#close-company').addEventListener('click',()=>$('#company-dialog').close());
$('#company-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{try{const result=await api('/api/companies',Object.fromEntries(new FormData(ev.target)));state.tax=result.tax;localStorage.setItem('somua-company',state.tax);await loadCompanies();await refresh();$('#company-dialog').close();ev.target.reset();toast('Đã tạo hồ sơ công ty. Bạn có thể nhập dữ liệu.');}catch(error){$('#company-error').textContent=error.message;}});});
async function useDemo(){await action(async()=>{const result=await api('/api/demo',{period:state.period});state.tax=result.tax;localStorage.setItem('somua-company',state.tax);await loadCompanies();await refresh();toast('Đã mở 10 hóa đơn mẫu: 7 khớp, 1 chênh lệch tiền, 2 thiếu XML. Dữ liệu mẫu được tách riêng.');});}
$('#demo-button').addEventListener('click',useDemo);$('#empty-demo').addEventListener('click',useDemo);
$('#period').value=state.period;$('#period').addEventListener('change',()=>action(async()=>{if(!$('#period').value)return;state.period=$('#period').value;localStorage.setItem('somua-period',state.period);await refresh();}));
$('#export').addEventListener('click',()=>{if(!state.report?.results.length)return;window.location.assign(`/api/export?tax=${encodeURIComponent(state.tax)}&period=${state.period}`);toast('Đang tạo Excel gồm 6 sheet. Các dòng ngoại lệ được tô màu để kiểm tra.');});
function filter(value){state.filter=value;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('active',x.dataset.filter===value));renderRows();}
document.querySelectorAll('[data-filter]').forEach(x=>x.addEventListener('click',()=>filter(x.dataset.filter)));
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{state.view=button.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b===button));const title={overview:'Tổng quan mua vào',invoices:'Hóa đơn mua vào',exceptions:'Hóa đơn cần kiểm tra'}[state.view];$('#page-title').textContent=title;$('#breadcrumb-current').textContent={overview:'Tổng quan',invoices:'Hóa đơn mua vào',exceptions:'Cần kiểm tra'}[state.view];filter(state.view==='exceptions'?'exception':'all');if(state.view!=='overview')$('.invoice-panel').scrollIntoView({behavior:'smooth',block:'start'});}));
$('#search').addEventListener('input',renderRows);
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();}});
action(async()=>{await loadCompanies();await refresh();});
