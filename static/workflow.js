/* Local processing workflows. All network calls remain on this machine. */
const fieldNames={buyer_tax:'MST người mua',seller_tax:'MST người bán',seller:'Tên người bán',serial:'Ký hiệu hóa đơn',number:'Số hóa đơn',date:'Ngày hóa đơn',net:'Tiền trước thuế',vat:'VAT',total:'Tổng thanh toán',currency:'Loại tiền',rate:'Tỷ giá',kind:'Loại hóa đơn',status:'Trạng thái đặc biệt'};
let pendingCqt=null;
function scope(){return {tax:state.tax,period:state.period};}
function fileURL(path,fingerprint){return `${path}?tax=${encodeURIComponent(state.tax)}&period=${state.period}&fingerprint=${encodeURIComponent(fingerprint)}`;}
function dialogMarkup(id,title,body,wide=false){let dialog=$('#'+id);if(!dialog){dialog=document.createElement('dialog');dialog.id=id;document.body.append(dialog);}dialog.className=wide?'wide-dialog':'medium-dialog';dialog.innerHTML=`<div class="dialog-heading"><div><div class="eyebrow">TRỢ LÝ HÓA ĐƠN MUA VÀO</div><h2>${e(title)}</h2></div><button type="button" class="close" aria-label="Đóng">×</button></div>${body}`;dialog.querySelector('.close').addEventListener('click',()=>dialog.close());return dialog;}
function renderWorkflow(){
 const r=state.report;$('#period-state').textContent=r?.closed?'Đã chốt kỳ':'Kỳ đang mở';$('#period-state').className='badge '+(r?.closed?'warning':'neutral');
 for(const selector of ['#settings-button','#history-button','#scan-button','#retry-button'])$(selector).disabled=state.busy||!state.tax;
 document.querySelectorAll('[data-review]').forEach(b=>{if(!b.dataset.bound){b.dataset.bound='1';b.addEventListener('click',()=>openReview(b.dataset.review));}});
}
function documentActions(row){
 const doc=row.document;const content=$('#document-content');
 const attachments=doc?.related_files?.length?doc.related_files:doc?.fingerprint?[{fingerprint:doc.fingerprint,filename:doc.filename,method:doc.method}]:[];
 if(!attachments.length)return;
 const box=document.createElement('div');box.className='file-links';
 box.innerHTML=attachments.map(f=>`<a class="button secondary" href="${fileURL('/api/file',f.fingerprint)}">↓ ${e(f.filename)}</a>${f.method==='xml'?`<a class="button secondary" href="${fileURL('/api/pdf',f.fingerprint)}">↓ PDF bản thể hiện</a>`:''}`).join('');
 if(doc.method!=='xml'&&doc.method){box.insertAdjacentHTML('beforeend',`<button class="button primary" id="review-document">${doc.needs_review?'Kiểm tra & xác nhận trích xuất':'Xem / sửa kết quả trích xuất'}</button>`);}
 content.append(box);$('#review-document')?.addEventListener('click',()=>{const fp=doc.fingerprint;$('#document-dialog').close();openReview(fp);});
 if(row.cqt.buyer_asserted){const note=document.createElement('p');note.className='reconciliation-note';note.textContent='MST người mua của danh sách CQT do người dùng xác nhận khi nhập; không lấy từ phiên CQT.';content.append(note);}
}
async function encodeFile(file){if(file.size>15_000_000)throw new Error('Mỗi file tối đa 15 MB');return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:file.name,data:reader.result.split(',')[1]});reader.onerror=()=>reject(new Error('Không đọc được '+file.name));reader.readAsDataURL(file);});}
['cqt','xml'].forEach(source=>{
 $(`#import-${source}`).addEventListener('click',()=>{if(state.report?.closed){toast('Kỳ đã chốt. Mở phiên bản mới trong Lịch sử kỳ để thay đổi.',true);return;}if(state.report?.company.demo){toast('Tạo công ty thật để nhập chứng từ; dữ liệu mẫu được tách riêng.',true);return;}$(`#file-${source}`).click();});
 $(`#file-${source}`).addEventListener('change',event=>action(async()=>{
  try{
   const files=Array.from(event.target.files);if(!files.length)return;
   if(source==='cqt'){
    const file=await encodeFile(files[0]);const preview=await api('/api/cqt-preview',{file});
    if(Object.keys(fieldNames).every(k=>preview.mapping[k]!=null)&&preview.headers.every(h=>Object.keys(fieldNames).includes(h))){const result=await api('/api/import',{...scope(),source,files:[file]});await refresh();toast(`Đã nhập ${result.added} hóa đơn; bỏ qua ${result.filtered} dòng ngoài kỳ.`);}
    else openMapping(file,preview);
   }else{
    if(files.length>100)throw new Error('Tối đa 100 file/lượt. Dùng quét thư mục cho kho lớn.');
    $('#job-progress').hidden=false;let counts={added:0,cached:0,failed:0,filtered:0};
    for(let index=0;index<files.length;index++){
     $('#job-title').textContent=`Đọc chứng từ ${index+1}/${files.length}`;$('#job-detail').textContent=files[index].name;
     const file=await encodeFile(files[index]);const result=await api('/api/import',{...scope(),source,files:[file]});for(const k of Object.keys(counts))counts[k]+=result[k]||0;
    }
    await refresh();toast(`Đã đọc ${counts.added} · có sẵn ${counts.cached} · lỗi ${counts.failed} · ngoài kỳ ${counts.filtered}.`,Boolean(counts.failed));
   }
  }finally{event.target.value='';$('#job-progress').hidden=true;}
 }));
});
function openMapping(file,preview){
 pendingCqt={file,preview};
 const body=`<p class="settings-explain">Tìm thấy ${preview.row_count} dòng. Kiểm tra ánh xạ cột trước khi nhập. Chỉ lấy hóa đơn đúng kỳ ${e(state.period)}; MST khác công ty sẽ bị từ chối.</p><form id="mapping-form"><div class="mapping-grid">${Object.entries(fieldNames).map(([key,label])=>`<label>${e(label)}${['seller_tax','serial','number','date','total'].includes(key)?' *':''}<select name="${key}"><option value="">Không có cột</option>${preview.headers.map((h,i)=>`<option value="${i}" ${preview.mapping[key]===i?'selected':''}>${e(h||'(Cột trống)')}</option>`).join('')}</select></label>`).join('')}</div><label class="check-line"><input type="checkbox" name="confirm_buyer">Tôi xác nhận danh sách thuộc MST ${e(state.tax)}. Chỉ áp dụng cho dòng không có MST người mua; không ghi đè MST đã có.</label><p class="form-error" id="mapping-error"></p><div class="modal-actions"><button class="button primary" type="submit">Nhập & đối chiếu</button></div></form>`;
 const dialog=dialogMarkup('mapping-dialog','Kiểm tra danh sách CQT',body,true);dialog.showModal();
 $('#mapping-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{try{const form=new FormData(ev.target);const mapping=Object.fromEntries(Object.keys(fieldNames).map(k=>[k,form.get(k)===''?null:Number(form.get(k))]));const result=await api('/api/import',{...scope(),source:'cqt',files:[file],mapping,header_row:preview.header_row,confirm_buyer:form.has('confirm_buyer')});dialog.close();await refresh();toast(`Đã nhập ${result.added} hóa đơn; bỏ qua ${result.filtered} dòng ngoài kỳ.`);}catch(error){$('#mapping-error').textContent=error.message;}});});
}
async function openReview(fingerprint){await action(async()=>{
 const data=await api(fileURL('/api/candidate',fingerprint));const record=data.record;
 const body=`<p class="settings-explain">Đối chiếu trực tiếp với chứng từ trước khi xác nhận. Dữ liệu PDF/OCR luôn chờ duyệt; không tự coi là đúng. File: ${e(data.filename)}</p><a class="button secondary" href="${fileURL('/api/file',fingerprint)}">↓ Tải file gốc để xem</a><form id="review-form"><div class="form-grid">${Object.entries(fieldNames).map(([key,label])=>`<label>${e(label)}<input name="${key}" value="${e(record[key]||'')}" ${key==='date'?'type="date"':''} ${['buyer_tax','seller_tax','serial','number','date','total','seller'].includes(key)?'required':''}></label>`).join('')}<label class="full-width">Chi tiết hàng hóa nguyên văn · mỗi dòng: Tên hàng | Số lượng | ĐVT | Đơn giá | Thành tiền<textarea name="items" rows="5" required>${e((record.items||[]).map(i=>[i.name,i.quantity,i.unit,i.price||'',i.amount].join(' | ')).join('\n'))}</textarea></label></div><details><summary>Văn bản trích xuất từ file</summary><pre class="extracted-text">${e(record.extracted_text||'Không có văn bản trích xuất. Bạn có thể nhập lại từ file gốc.')}</pre></details><label class="check-line"><input type="checkbox" required>Tôi đã xem file nguồn và xác nhận các trường trên đúng với chứng từ.</label><p id="review-error" class="form-error"></p><div class="modal-actions"><button class="button primary" type="submit">Xác nhận & đối chiếu lại</button></div></form>`;
 const dialog=dialogMarkup('review-dialog','Kiểm tra dữ liệu chứng từ',body,true);dialog.showModal();
 $('#review-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{try{const form=new FormData(ev.target);const record=Object.fromEntries(Object.keys(fieldNames).map(k=>[k,form.get(k)]));record.items=String(form.get('items')).split('\n').filter(x=>x.trim()).map(line=>{const [name,quantity='',unit='',price='',amount='']=line.split('|').map(x=>x.trim());return {name,quantity,unit,price,amount};});await api('/api/review',{...scope(),fingerprint,record});dialog.close();await refresh();toast('Đã lưu xác nhận và cập nhật đối chiếu.');}catch(error){$('#review-error').textContent=error.message;}});});
});}
$('#settings-button').addEventListener('click',()=>action(async()=>{
 const config=await api(`/api/settings?tax=${state.tax}`);
 const body=`<p class="settings-explain">Các thư mục nằm trên máy đang chạy ứng dụng. Kho từng công ty phải tách riêng. Mọi xử lý diễn ra cục bộ; không gửi chứng từ tới AI bên ngoài.</p><form id="settings-form"><label class="check-line"><input type="checkbox" name="enabled" ${config.enabled?'checked':''}>Bật xử lý hàng loạt cho công ty này</label><label>Thư mục chứng từ gốc<input name="source_folder" value="${e(config.source_folder)}" placeholder="Ví dụ: D:\\HoaDon\\${e(state.tax)}"></label><label>Thư mục xuất Excel<input name="output_folder" value="${e(config.output_folder)}" placeholder="Ví dụ: D:\\BangKe\\${e(state.tax)}"></label><h3>Quy tắc trình bày tên hàng</h3><p class="settings-explain">Chỉ đổi tên trên bảng kê chính. Giữ nguyên chi tiết gốc. Ví dụ: “dịch vụ ăn uống” → “Chi phí tiếp khách”.</p><div id="rules-list"></div><button type="button" class="button secondary" id="add-rule">＋ Thêm quy tắc</button><label class="check-line"><input type="checkbox" name="approve_rules" ${config.rules.length?'checked':''}>Tôi phê duyệt các quy tắc trên cho công ty này.</label><p id="settings-error" class="form-error"></p><div class="modal-actions"><button class="button primary" type="submit">Lưu cấu hình</button></div></form>`;
 const dialog=dialogMarkup('settings-dialog','Cấu hình công ty',body);dialog.showModal();
 const addRule=rule=>{const row=document.createElement('div');row.className='rule-row';row.innerHTML=`<input class="rule-keyword" placeholder="Từ khóa trên hóa đơn" value="${e(rule.keyword||'')}"><input class="rule-label" placeholder="Tên trình bày trên bảng kê" value="${e(rule.label||'')}"><button class="button secondary" type="button">×</button>`;row.querySelector('button').addEventListener('click',()=>row.remove());$('#rules-list').append(row);};
 config.rules.forEach(addRule);$('#add-rule').addEventListener('click',()=>addRule({}));
 $('#settings-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{try{const form=new FormData(ev.target);const rules=Array.from(document.querySelectorAll('.rule-row')).map(row=>({keyword:row.querySelector('.rule-keyword').value,label:row.querySelector('.rule-label').value,approved:form.has('approve_rules')}));await api('/api/settings',{tax:state.tax,enabled:form.has('enabled'),source_folder:form.get('source_folder'),output_folder:form.get('output_folder'),rules});dialog.close();await refresh();toast('Đã lưu cấu hình cho công ty đang chọn.');}catch(error){$('#settings-error').textContent=error.message;}});});
}));
async function runJob(path){await action(async()=>{
 if(state.report?.closed&&path!=='/api/batch')throw new Error('Kỳ đã chốt. Mở phiên bản mới trước khi xử lý lại.');
 const {id}=await api(path,scope());$('#job-progress').hidden=false;
 try{
  let job;do{await new Promise(resolve=>setTimeout(resolve,500));job=await api('/api/job?id='+id);$('#job-title').textContent=`Đang xử lý công ty ${job.company||''}`;$('#job-detail').textContent=job.file||'Đang chuẩn bị / xử lý lại file lỗi…';}while(job.state==='running');
  await refresh();const failures=job.results.filter(r=>r.error);const rejected=job.results.reduce((n,r)=>n+(r.result?.rejected||0),0);toast(failures.length?job.results.map(r=>`${r.tax}: ${r.error||'hoàn tất'}`).join(' · '):`Hoàn tất ${job.results.length} công ty · ${rejected} file bị từ chối. Kiểm tra ngoại lệ và xuất Excel.`,Boolean(failures.length||rejected));
 }finally{$('#job-progress').hidden=true;}
});}
$('#scan-button').addEventListener('click',()=>runJob('/api/scan'));$('#retry-button').addEventListener('click',()=>runJob('/api/retry'));$('#batch-button').addEventListener('click',()=>runJob('/api/batch'));
$('#history-button').addEventListener('click',()=>showHistory());
async function showHistory(){await action(async()=>{
 const history=await api(`/api/history?tax=${state.tax}&period=${state.period}`);const audit=await api(`/api/audit?tax=${state.tax}&period=${state.period}`);
 const body=`<p class="settings-explain">Mỗi lần lưu giữ một bản Excel riêng. Chốt kỳ khóa các thao tác nhập và sửa; mở phiên bản mới giữ nguyên các bản cũ. Chỉ chốt khi không còn ngoại lệ, file lỗi hoặc chứng từ ngoài danh sách.</p><div class="modal-actions"><button class="button secondary" id="save-version">Lưu phiên bản</button><button class="button secondary" id="save-folder">Lưu Excel vào thư mục</button>${state.report?.closed?'<button class="button primary" id="reopen-period">Mở phiên bản mới</button>':'<button class="button primary" id="close-period">Chốt kỳ</button>'}</div><p class="form-error" id="history-error"></p><p class="settings-explain"><a href="/api/backup">↓ Sao lưu cơ sở dữ liệu toàn bộ công ty</a> · Bản sao chứa chứng từ và số liệu kế toán; giữ trong nơi riêng tư.</p><h3>Phiên bản đã lưu</h3>${history.map(r=>`<div class="history-row"><div><strong>v${r.version} ${r.closed?'· Đã chốt':''}</strong><small>${e(new Date(r.time).toLocaleString('vi-VN'))}</small></div><a class="button secondary" href="/api/revision?tax=${state.tax}&period=${state.period}&id=${r.id}">↓ Excel</a></div>`).join('')||'<p>Chưa lưu phiên bản nào.</p>'}<h3>Nhật ký xử lý</h3>${audit.map(a=>`<div class="audit-row"><small>${e(new Date(a.time).toLocaleString('vi-VN'))}</small><strong>${e(a.event)}</strong><details><summary>Chi tiết</summary>${e(a.detail)}</details></div>`).join('')||'<p>Chưa có thao tác.</p>'}`;
 const dialog=dialogMarkup('history-dialog',`Lịch sử kỳ ${state.period}`,body);dialog.showModal();
 const bind=(id,path,extra)=>$(id)?.addEventListener('click',()=>action(async()=>{try{const result=await api(path,{...scope(),...extra});await refresh();dialog.close();toast(result.filename?`Đã lưu ${result.filename}`:'Đã lưu trạng thái kỳ. Các phiên bản cũ được giữ nguyên.');}catch(error){$('#history-error').textContent=error.message;}}));
 bind('#save-version','/api/version',{});bind('#save-folder','/api/save-export',{});bind('#close-period','/api/version',{closed:true});bind('#reopen-period','/api/reopen',{});
});}

$('#open-cqt-button').addEventListener('click',()=>action(async()=>{if(!state.tax)throw new Error('Chọn công ty trước khi mở CQT');if(state.report?.company.demo)throw new Error('Không mở CQT cho công ty mẫu');const result=await api('/api/open-cqt',{tax:state.tax});toast(result.message);}));
