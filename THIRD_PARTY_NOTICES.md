# Thành phần bên thứ ba

Gói Windows chứa các wheel chính thức được tải từ PyPI: openpyxl, et-xmlfile, pypdf, reportlab, Pillow, pypdfium2 và charset-normalizer. Metadata, giấy phép và thông báo bản quyền của mỗi gói được giữ nguyên trong `.whl` ở `vendor/windows`; pypdfium2 chứa PDFium và các thông báo liên quan trong chính wheel. Manifest `requirements-windows.txt` khóa phiên bản và SHA-256, được BAT yêu cầu kiểm tra khi cài.

Font DejaVuSans được kèm để hiển thị PDF tiếng Việt. Giấy phép và thông báo bản quyền nằm tại `assets/FONT-LICENSE.txt`.

Tesseract và Python không được đóng gói thành binary trong ZIP này. Người dùng cài các runtime đó riêng khi cần. Chromium/Playwright chỉ dùng để kiểm thử trong môi trường phát triển, không nằm trong gói Windows.
