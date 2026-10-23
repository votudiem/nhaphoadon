# Thành phần bên thứ ba

Gói Windows chứa các wheel chính thức được tải từ PyPI: openpyxl, et-xmlfile, pypdf, reportlab, Pillow, pypdfium2 và charset-normalizer. Metadata, giấy phép và thông báo bản quyền của mỗi gói được giữ nguyên trong `.whl` ở `vendor/windows`; pypdfium2 chứa PDFium và các thông báo liên quan trong chính wheel. Manifest `requirements-windows.txt` khóa phiên bản và SHA-256, được BAT yêu cầu kiểm tra khi cài.

Font DejaVuSans được kèm để hiển thị PDF tiếng Việt. Giấy phép và thông báo bản quyền nằm tại `assets/FONT-LICENSE.txt`.

Công cụ uv 0.12.23 được đóng gói dưới dạng wheel chính thức trong `vendor/bootstrap`, giữ nguyên license/metadata trong wheel; `bootstrap-tools.json` ghi SHA-256 trước khi trích xuất executable. Python chạy app được uv tải riêng khi cần; không gộp runtime đó vào ZIP. Tesseract cài riêng khi cần OCR. Chromium/Playwright chỉ dùng để kiểm thử trong môi trường phát triển, không nằm trong gói Windows.
