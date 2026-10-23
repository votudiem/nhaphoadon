# Sổ Mua — Trợ lý hóa đơn mua vào · bản cục bộ 1.0

Ứng dụng một trang bằng tiếng Việt, chạy và lưu chứng từ trên máy kế toán. Được xây mới theo đặc tả của người dùng và hồ sơ bàn giao V9.2; không phải mã nguồn AppDeploy được khôi phục.

**Bắt đầu:** xem `HUONG_DAN_SU_DUNG.md`. Trên Windows 64-bit có Python 3.12, giải nén gói Windows rồi bấm `BAT_DAU_WINDOWS.bat`. Gói Windows có sẵn dependency, được kiểm tra SHA-256 khi cài; không cần tải thư viện từ mạng. OCR cần Tesseract riêng; nếu chưa cài vẫn có thể đọc PDF text/XML và kiểm tra, nhập lại dữ liệu ảnh từ file gốc.

## Đã có

- Quản lý nhiều công ty theo MST; cấu hình thư mục, bật/tắt batch, kỳ kế toán và quy tắc riêng.
- Nhập danh sách CQT CSV/XLSX; tự tìm tiêu đề và có màn hình ánh xạ cột. Xác nhận nguồn khi file không có MST người mua; không ghi đè MST khác đã có trong file. Lọc đúng tháng, chặn khóa CQT trùng.
- Đọc XML; lấy văn bản PDF trước; OCR ảnh/PDF scan tại máy. PDF/OCR luôn chờ người dùng xác nhận; không tự khẳng định dữ liệu đúng. Có xem văn bản trích xuất, tải file gốc, sửa trường dữ liệu và lưu lịch sử xác nhận.
- Quét thư mục; cache theo đường dẫn, kích thước, mtime và SHA-256; chỉ xử lý lại file mới/thay đổi. File thay đổi thay dữ liệu hoạt động, giữ raw gốc trong kho lưu. File đã đọc trong các tháng trước có thể dùng lại; không sửa file nguồn. Lưu tiến độ từng file khi quét, tiếp tục dùng cache ở lần sau.
- Phân biệt file đọc lỗi, chưa tìm thấy chứng từ, trùng khóa, chênh tiền/ngày/loại tiền/tỷ giá, chờ duyệt trích xuất và chứng từ ngoài CQT. Không suy ra “thiếu file thực sự” từ việc chưa ghép được.
- Khóa ghép gồm MST người mua/người bán, ký hiệu và số HĐ; kiểm tra ngày, tiền và tỷ giá. Giữ số 0 đầu; hiểu dạng `1K26THT`/`K26THT`. Ưu tiên XML khi cùng hóa đơn có PDF và giữ tất cả file liên quan. Nhiều XML hoặc nhiều PDF ngang nhau phải kiểm tra.
- Xuất Excel 6 sheet, một hóa đơn CQT một dòng; giữ chi tiết mặt hàng nguyên văn và ngoại lệ. Tiền dùng Decimal trong xử lý, Excel kiểu số; số HĐ/MST/ký hiệu kiểu text. Không tự suy ra VAT hóa đơn bán hàng; ngoại tệ có cột tỷ giá, chưa tự quy đổi VND.
- Sinh PDF bản thể hiện XML với font tiếng Việt. Khi quét và có thư mục xuất, tự lưu vào `_PDF_CQT`; không quét lại thư mục này, không nhập PDF do chính app sinh vào engine.
- Quét batch tuần tự; lỗi một công ty vẫn tiếp tục công ty khác. Tự tạo phiên bản Excel vào thư mục xuất nếu có danh sách CQT. Xử lý lại riêng file lỗi; không chạy lại file thành công.
- Lịch sử phiên bản, tải lại Excel cũ, chốt kỳ, mở phiên bản mới và nhật ký. Không cho chốt khi còn ngoại lệ/file lỗi/chứng từ ngoài danh sách. Bản đã chốt khóa nhập/sửa; các phiên bản cũ được giữ.
- Quy tắc tên hàng phải được duyệt, chỉ đổi trên bảng kê chính; giữ nguyên nội dung sheet chi tiết. Nếu nhiều nhãn mâu thuẫn, đưa vào ngoại lệ.
- Sao lưu SQLite từ giao diện. Mở trang CQT chính thức bằng Chrome profile riêng theo MST trên máy có desktop; không điền username/password/CAPTCHA, không tự đăng nhập lại.

## Phần cần tiếp tục kiểm chứng

**Chưa có đồng bộ CQT tự động, kiểm tra MST của phiên đăng nhập, tải XML từ CQT/rate limit/resume theo API.** Nút Mở CQT chỉ mở Chrome riêng và trạng thái phiên luôn chưa xác minh. Danh sách CQT hiện lấy bằng nhập CSV/Excel. Môi trường cloud bị proxy từ chối kết nối tới cổng CQT; chưa có phiên người dùng để kiểm thử. Không được trình bày bản này là đã hoàn thành luồng một nút tự tải CQT.

Chưa kiểm tra chữ ký số/tính hợp lệ thuế XML; không tự xử lý nghiệp vụ hóa đơn điều chỉnh/thay thế/hủy. Bộ parser PDF là bộ gợi ý theo nhãn, không bảo đảm mọi mẫu nhà cung cấp; dữ liệu PDF/OCR và tên hàng cần duyệt thủ công. PDF scan giới hạn 5 trang, PDF text tối đa 50 trang; mỗi file tối đa 15 MB. Không có AI bên ngoài. Chưa nghiệm thu bộ 405 dòng/374 file Huệ Duy vì chưa được cung cấp. Chưa chạy trực tiếp trên Windows hoặc Microsoft Excel; kiểm thử thực tế hiện là Linux, Chromium và openpyxl. Đây là bản cục bộ, chưa triển khai website công khai hoặc tạo bộ cài `.exe`.

## Phát triển và kiểm thử

Python 3.12+ trên Linux:

```sh
cd /workspace/nhaphoadon
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python app.py
```

Máy chủ chỉ bind `127.0.0.1:8765`, kiểm tra Host/Origin và header riêng cho thao tác ghi. Mở trình duyệt trên cùng máy với host/cổng này. Không mở máy chủ ra LAN/Internet. Chạy `python tests/browser_smoke.py` và `python tests/browser_extended.py` khi có Playwright và Chromium tại `/usr/bin/chromium`; kiểm thử dùng SQLite/thư mục tạm, không dùng dữ liệu người dùng.

Dữ liệu nằm trong `.data/invoices.sqlite`, gồm raw chứng từ và lịch sử. `INVOICE_DATA_DIR` đổi vị trí. Chrome profile nằm riêng trong `.data/browser_profiles/<MST>`, chứa phiên nhạy cảm; không đưa vào Git hoặc gửi cho người khác. Không sửa/xóa `.data` khi cập nhật app. Không đẩy chứng từ thật lên repository công khai.
