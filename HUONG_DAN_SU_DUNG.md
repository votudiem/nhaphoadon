# Hướng dẫn Sổ Mua trên máy kế toán

## 1. Mở ứng dụng

1. Cài **Python 3.12, bản Windows 64-bit**, từ python.org, bật Python Launcher khi cài. Đây là điều kiện để chạy gói Python, không phải bộ cài EXE độc lập.
2. Giải nén toàn bộ `So_Mua_1_0_Windows.zip` vào thư mục riêng, ví dụ `D:\SoMua`. Không chạy ngay bên trong cửa sổ ZIP.
3. Bấm đúp `BAT_DAU_WINDOWS.bat`. Lần đầu ứng dụng tạo môi trường Python riêng và cài dependency từ thư mục `vendor/windows` đã đóng gói, có kiểm tra checksum.
4. Trình duyệt tự mở giao diện. Giữ cửa sổ lệnh đang chạy; đóng cửa sổ này sẽ dừng app. Lần mở tiếp theo có thể bấm lại file BAT; launcher dùng lại app đang chạy nếu đúng là Sổ Mua.

Không tải được Python hoặc script báo lỗi? Giữ nội dung lỗi ở cửa sổ. Chưa có bằng chứng chạy BAT trên Windows trong đợt bàn giao này; Linux và Chromium đã được kiểm thử. Cổng mặc định là 8765; nếu ứng dụng khác đang chiếm cổng, không dừng ứng dụng đó tùy tiện. Người hỗ trợ có thể chạy `python app.py --port 8766 --open` trong môi trường đã cài dependency.

## 2. Thử quy trình không dùng hóa đơn thật

Bấm **Khám phá dữ liệu mẫu**. App tạo riêng công ty có nhãn mẫu, gồm 10 dòng: 7 khớp, 1 chênh tiền, 2 chưa có chứng từ. Không có kết nối CQT thật trong dữ liệu mẫu. Nhấn dòng để xem hai nguồn; bấm Xuất Excel để xem đủ các sheet.

## 3. Khai báo công ty và kỳ

Bấm **Thêm công ty**, nhập tên và MST người mua. Mỗi công ty có dữ liệu, cấu hình và Chrome profile riêng. Chọn kỳ tháng trước khi nhập dữ liệu.

Trong **Cấu hình công ty**, chọn bằng cách nhập đường dẫn tuyệt đối tới thư mục chứng từ và thư mục xuất đã tồn tại trên máy chạy app. Các kho của công ty khác nhau không được trùng hoặc chồng lấn. Có thể bỏ trống thư mục và chỉ nhập file/tải Excel bằng trình duyệt. Bật/tắt xử lý batch tại đây.

## 4. Nhập danh sách CQT

Dùng **Nhập CQT**, chọn CSV UTF-8 hoặc XLSX. Nếu có XLS cũ, mở bằng Excel và lưu thành XLSX trước. App tìm tiêu đề trong 30 dòng đầu và cho kiểm tra ánh xạ cột. Nếu tiêu đề không nhận diện được, dùng **Mẫu CSV** và điền đúng cột mẫu.

Các trường bắt buộc: MST người bán, ký hiệu, số hóa đơn, ngày, tổng thanh toán. Nên có tên người bán, tiền trước thuế, VAT, loại tiền, tỷ giá, loại và trạng thái hóa đơn. Thiếu MST người mua thì phải đánh dấu xác nhận danh sách thuộc công ty đang chọn; nguồn xác nhận này sẽ được ghi nhận, không giả làm dữ liệu lấy từ phiên CQT. Có MST khác trong bất kỳ dòng nào thì từ chối nhập. Dòng ngoài tháng được báo và bỏ qua; khóa trùng bị từ chối. Nhập lại thay danh sách CQT tháng đó, không xóa kho chứng từ.

Với mẫu CSV tiếng Anh: `buyer_tax,seller_tax,seller,serial,number,date,net,vat,total,currency,rate,kind,status`. Ngày `YYYY-MM-DD`, tiền dạng `1080000.50`, không phân cách hàng nghìn; `kind=sales` cho hóa đơn bán hàng, `currency=VND` mặc định. Giữ số hóa đơn/MST kiểu Text trong Excel. App giữ giá trị chuỗi và phục hồi zero-padding khi ô số có định dạng `00000000`; không thể biết số 0 đã mất từ trước nếu file không có thông tin đó.

## 5. Đọc kho và đối chiếu

- **Nhập chứng từ** nhận XML/PDF/JPG/JPEG/PNG, tối đa 100 file/lượt, 15 MB/file, xử lý tuần tự và báo tiến độ.
- **Quét kho & đối chiếu** quét thư mục đã lưu, bỏ qua thư mục ẩn và `_PDF_CQT`. File không đổi dùng cache. Quét lưu tiến độ từng file; nếu phải dừng, lần sau dùng lại phần đã lưu.
- PDF text được đọc trực tiếp trước, không đưa qua OCR nếu đã có văn bản. Ảnh/PDF scan dùng OCR tại máy nếu có Tesseract.
- PDF/OCR chỉ gợi ý các trường; luôn có trạng thái chờ xác nhận. Bấm hóa đơn → **Kiểm tra & xác nhận trích xuất**, tải file gốc và so lại từng trường. Nhập chi tiết mặt hàng nguyên văn theo hướng dẫn trong form rồi đánh dấu đã kiểm tra. Nếu chưa xác định được danh tính hóa đơn, file nằm trong **Ngoài bảng kê CQT** để kiểm tra riêng.
- XML được ưu tiên làm nguồn chính khi cùng hóa đơn có PDF. Không sửa dữ liệu XML qua form; nếu XML hỏng, thay bằng file đúng ở kho và quét lại.

OCR tùy chọn: cài Tesseract OCR với dữ liệu `vie` và `eng`, đưa lệnh `tesseract` vào PATH rồi mở lại app. Nếu chỉ có tiếng Anh, OCR vẫn có thể đọc nhưng dễ sai dấu tiếng Việt và vẫn phải kiểm tra. Không có Tesseract thì giữ file lỗi để nhập tay từ nguồn; không tự gửi tới AI bên ngoài.

## 6. Kiểm tra ngoại lệ và xuất

Dashboard đếm theo dòng CQT; file đọc lỗi chưa xác định danh tính nằm riêng, không tự tính thành hóa đơn “thiếu thực sự”. Một hóa đơn có thể có nhiều lý do ngoại lệ nhưng chỉ một dòng bảng kê. Nhấn dòng để so dữ liệu, tải file gốc hoặc PDF bản thể hiện XML.

**Xử lý lại riêng file lỗi** chỉ chạy lại các raw file đã lỗi. Nếu bạn thay nội dung file ở thư mục, dùng Quét kho để nhận nội dung mới. Dữ liệu xác nhận PDF/OCR được lưu riêng, raw gốc không đổi.

**Xuất Excel** tải bản hiện tại. Nếu có thư mục xuất, quét kho hoặc xử lý lại sẽ tạo thêm phiên bản Excel trong thư mục đó khi có danh sách CQT; PDF sinh từ XML vào `_PDF_CQT`. **Xử lý các công ty đã cấu hình** chạy tuần tự, bỏ qua công ty lỗi rồi tiếp tục công ty khác; không đồng nghĩa tải CQT tự động.

Sáu sheet: `BangKe_MuaVao`, `NgoaiLe`, `ChiTiet_HoaDon`, `CQT_ChuanHoa`, `HoaDon_DocDuoc`, `Log_XuLy`. Ba sheet kỹ thuật cuối có thể bị ẩn; dùng Unhide trong Excel để xem. Dòng ngoại lệ tô màu. Tiền hiển thị theo nguyên tệ; không cộng hoặc tự quy đổi nhiều loại tiền.

## 7. Lịch sử, chốt kỳ, quy tắc và sao lưu

Trong **Lịch sử kỳ**, lưu phiên bản, tải Excel cũ, lưu Excel vào thư mục hoặc chốt kỳ. Chốt bị từ chối nếu còn ngoại lệ/file lỗi/chứng từ ngoài danh sách. Muốn bổ sung sau chốt, bấm **Mở phiên bản mới**; các file phiên bản cũ vẫn tải được. Nhật ký ghi thao tác nhập, quét, sửa kết quả và đóng/mở kỳ.

Quy tắc trình bày tên hàng nằm trong cấu hình công ty và chỉ áp dụng khi bạn phê duyệt. Nội dung nguyên văn vẫn ở sheet chi tiết; nhiều quy tắc cho nhãn khác nhau sẽ báo ngoại lệ, không tự chọn.

Link **Sao lưu cơ sở dữ liệu toàn bộ công ty** trong Lịch sử kỳ tải một bản SQLite nhất quán, chứa chứng từ và lịch sử. Giữ file ở nơi riêng tư. Để khôi phục: dừng app hoàn toàn, giữ lại bản `.data/invoices.sqlite` cũ ở vị trí an toàn, sao chép file backup thành `.data/invoices.sqlite`, rồi mở lại. Không trộn hai database. Sao lưu SQLite không bao gồm Chrome profile; phiên CQT cần đăng nhập lại.

## 8. CQT: ranh giới hiện tại

**Mở CQT** chỉ mở trang chính thức trong Chrome profile riêng theo MST trên máy có desktop. Bạn tự đăng nhập; app không điền, lưu hoặc retry mật khẩu/CAPTCHA. Không cung cấp tài khoản/mật khẩu thuế qua chat.

App hiện chưa kiểm tra MST đang đăng nhập, chưa tự tải danh sách/XML từ CQT và chưa triển khai xử lý 429 CQT. Phần này cần kiểm thử tích hợp bằng phiên đăng nhập hợp lệ trên Windows; không thể thay bằng dữ liệu mẫu. Bộ Huệ Duy 405 dòng và 374 file cũng chưa được cung cấp để nghiệm thu thực tế. Vì vậy bản cục bộ này chưa phải nghiệm thu toàn bộ luồng tự động trong đặc tả gốc.
