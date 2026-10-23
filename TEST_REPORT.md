# Báo cáo kiểm chứng · Sổ Mua cục bộ 1.1

Ngày: 23/10/2026. Môi trường thực thi: Linux, Python 3.12.14, Chromium headless. Dữ liệu thử được tạo tổng hợp; không chứa bộ hóa đơn thật Huệ Duy. Đây là bản mới, không phải source AppDeploy V9.2.

## Kết quả đã thực hiện

| Kiểm tra | Kết quả |
|---|---|
| `python -m unittest discover -s tests -v` | 33 bài passed, 0 failed, 0 skipped trên máy kiểm thử có Tesseract |
| `pip check` | Không có dependency hỏng |
| Biên dịch Python, kiểm tra cú pháp hai file JavaScript | Passed |
| `tests/browser_smoke.py` | Passed: dữ liệu mẫu, lọc/tìm kiếm, đối chiếu, tạo công ty, CSV/XML, Excel, tải lại giữ dữ liệu và màn hình 390px; không có lỗi JS |
| `tests/browser_extended.py` | Passed: ánh xạ XLSX, xác nhận nguồn MST, PDF text, người dùng duyệt, cấu hình/rules, quét có tiến độ, tự sinh PDF/Excel, chốt/mở kỳ, retry file lỗi và backup; không có lỗi JS |
| OCR thật | Gọi tiến trình Tesseract tại máy, đọc được số hóa đơn/MST từ ảnh tổng hợp. Máy hiện có ngôn ngữ eng; chất lượng OCR tiếng Việt thực tế chưa được nghiệm thu |
| Dependency Windows | Tải đủ 7 wheel từ PyPI qua TLS, kiểm tra CRC wheel và tạo manifest SHA-256; gói dành riêng Python 3.12 Windows x64 |

Các bài kiểm thử kiểm chứng:

- Giữ số hóa đơn `00000057` từ XML/CSV và ô Excel định dạng `00000000` đến file xlsx đầu ra.
- Chặn dữ liệu sai MST, tách tháng, từ chối khóa CQT trùng; giữ dữ liệu cũ khi lượt nhập không hợp lệ.
- Nhận XML/PDF cùng hóa đơn thành một dòng; ưu tiên XML, giữ cả hai nguồn. Nhiều ứng viên ngang nhau là ngoại lệ.
- So sánh tiền/ngày/loại tiền/tỷ giá, giữ nguyên chi tiết hàng, áp nhãn trình bày chỉ khi rule được duyệt, không suy ra VAT hóa đơn bán hàng.
- File lỗi không tự tính là thiếu chứng từ. Retry chỉ gọi parser với file lỗi, giữ file thành công.
- Cache theo đường dẫn/metadata/hash. File thay đổi thay kết quả hoạt động và vẫn lưu raw gốc trong kho.
- Sinh PDF tiếng Việt từ XML, đọc lại số hóa đơn và tên hàng; PDF do app sinh bị loại khỏi engine.
- Excel mở lại bằng openpyxl có 6 sheet, kiểu dữ liệu đúng, freeze/filter, chuỗi bắt đầu bằng `=` không trở thành công thức.
- Chốt kỳ khóa nhập/sửa. Mở lại tạo phiên bản tiếp theo, giữ Excel cũ. Chưa giải quyết ngoại lệ thì không chốt.
- Batch thật qua HTTP: một công ty lỗi thư mục, công ty tiếp theo vẫn xử lý được. File gốc không tải được khi đổi sang MST khác. Backup là SQLite hợp lệ.
- Chặn POST thiếu header hoặc Origin không đúng.

## Chưa được xác nhận

- **Windows:** chưa thực thi BAT, Chrome profile hoặc wheel native trên Windows; không có `.exe` độc lập. Python hệ thống chỉ dùng mở bộ khởi tạo (3.10+); app chạy trong runtime CPython 3.12 riêng. Gói dependency đã chuẩn bị không thay cho kiểm thử máy đích.
- **CQT:** chưa kiểm tra được phiên đăng nhập/MST trên portal, chưa có tự tải danh sách/XML, chưa có rate-limit/resume của CQT. Nút mở CQT chỉ khởi chạy Chrome riêng. Thử HEAD tới cổng chính thức trong cloud bị proxy CONNECT 403. Đã lưu đề xuất thêm `hoadondientu.gdt.gov.vn` vào cấu hình mạng; cần user lưu/publish môi trường để áp dụng, chưa chứng minh runtime truy cập được.
- **Dữ liệu thật:** chưa có `Hóa đơn(2).rar` 77 MB và bảng kê đối chiếu tháng 07/2026 Huệ Duy, nên số liệu 405/374 trong hồ sơ bàn giao chưa được kiểm chứng lại.
- **Nghiệp vụ:** không xác minh chữ ký số XML hoặc kết luận tính hợp lệ/khấu trừ thuế; hóa đơn đặc biệt chỉ báo ngoại lệ. PDF/OCR là gợi ý và luôn cần người dùng xác nhận, không tự hiểu mọi mẫu bảng mặt hàng.
- **Excel thực tế:** đã kiểm tra cấu trúc/giá trị xlsx bằng openpyxl, chưa mở bằng Microsoft Excel trên Windows.
- **Triển khai:** chưa xuất bản website công khai, chưa sửa app AppDeploy cũ. Bản hiện tại phục vụ xử lý cục bộ; chưa đạt nghiệm thu toàn bộ luồng tự động trong đặc tả gốc.

## Tệp bàn giao

Gói Windows kèm source, thư viện cài offline có hash, font/license, launcher, hướng dẫn và bài kiểm thử. Gói source tách riêng không chứa vendor để tiện phát triển. Cả hai loại trừ `.data`, `.git`, `.venv`, hóa đơn thật, cookie và Chrome profile. Ảnh giao diện trong `artifacts/` chỉ dùng dữ liệu tổng hợp.

## Kiểm chứng bản sửa bộ khởi tạo 1.1

- Dùng Python **3.15.0rc3 trên Linux** để chạy thật `bootstrap.py --prepare-only`: tự tải CPython 3.12.15 riêng, tạo `.runtime/venv`, cài dependency và kiểm tra import native thành công. Đây là kiểm thử bộ khởi tạo bằng 3.15, không phải chạy trực tiếp thư viện app trên 3.15. Chưa có Windows/Python 3.15 của người dùng để thực thi tại chỗ.
- Chạy lại cùng Python 3.15 với `PIP_NO_INDEX=1 UV_OFFLINE=true`: chuẩn bị thành công, dùng lại runtime, không cần tải mạng.
- Thêm 9 bài regression kiểm tra nhận Python 3.15, tự phục hồi môi trường hỏng và giữ nguyên dữ liệu hóa đơn, khóa tránh chạy cài đặt đồng thời, kiểm checksum công cụ, sửa executable bị thay đổi từ wheel hợp lệ, cache dependency, cài wheel có hash, và không đánh dấu sẵn sàng nếu import native thất bại. Tổng 33 bài passed.
- Bộ khởi động BAT không còn yêu cầu `py -3.12` hoặc từ chối bản Python hệ thống khác 3.12. Python 3.12 là runtime nội bộ để khớp các thư viện native đã kiểm thử.
- Công cụ uv Windows 0.12.23 lấy từ wheel chính thức PyPI, SHA-256 trong `bootstrap-tools.json`; runtime tải bằng uv giữ xác minh TLS/checksum. Không sửa PATH/registry Python mặc định, không xóa `.venv` cũ hoặc `.data`.
