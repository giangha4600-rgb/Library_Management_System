"""Tạo tài khoản và dữ liệu mẫu cho hệ thống quản lý thư viện.
Chạy sau khi đã tạo các bảng bằng rechema.sql.
Script có thể chạy nhiều lần mà không tạo dữ liệu mẫu trùng lặp.
"""
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from app import query, db_connection

# -------------------- 1. TÀI KHOẢN MẪU --------------------
# Chỉ sử dụng hai vai trò: ThuThu và DocGia.
accounts = [
    ("thuthu123", "Giang@123", "Thủ thư mẫu", "ThuThu", None, "thuthu@library.local", "0900000001"),
    ("docgia", "DocGia@123", "Nguyễn Văn An", "DocGia", "DG0001", "an@example.com", "0900000002"),
    ("docgia02", "DocGia@123", "Trần Thị Bình", "DocGia", "DG0002", "binh@example.com", "0900000003"),
    ("docgia03", "DocGia@123", "Lê Minh Châu", "DocGia", "DG0003", "chau@example.com", "0900000004"),
    ("docgia04", "DocGia@123", "Phạm Quốc Dũng", "DocGia", "DG0004", "dung@example.com", "0900000005"),
    ("docgia05", "DocGia@123", "Hoàng Thu Hà", "DocGia", "DG0005", "ha@example.com", "0900000006"),
]

def get_available_card(preferred_card):
    """Dùng mã thẻ đề xuất nếu còn trống; nếu đã có thì tìm DG0001, DG0002... còn trống."""
    if not preferred_card:
        return None
    occupied = query("SELECT MaND FROM NguoiDung WHERE MaThe=?", (preferred_card,), one=True)
    if not occupied:
        return preferred_card

    number = 1
    while True:
        candidate = f"DG{number:04d}"
        occupied = query("SELECT MaND FROM NguoiDung WHERE MaThe=?", (candidate,), one=True)
        if not occupied:
            print(f"MaThe {preferred_card} đã được sử dụng; cấp mã thẻ thay thế {candidate}.")
            return candidate
        number += 1


for username, password, fullname, role, card, email, phone in accounts:
    existing = query("SELECT MaND FROM NguoiDung WHERE TenDangNhap=?", (username,), one=True)
    password_hash = generate_password_hash(password)
    if existing:
        query("""UPDATE NguoiDung
                 SET MatKhau=?, HoTen=?, VaiTro=?, Email=?, SoDienThoai=?,
                     TrangThaiTaiKhoan=1, TrangThaiThe=N'HoatDong'
                 WHERE TenDangNhap=?""",
              (password_hash, fullname, role, email, phone, username), commit=True)
        print("Updated account:", username)
    else:
        available_card = get_available_card(card)
        query("""INSERT INTO NguoiDung
                 (TenDangNhap,MatKhau,HoTen,VaiTro,MaThe,Email,SoDienThoai,
                  NgayCapThe,NgayHetHan,TrangThaiTaiKhoan)
                 VALUES(?,?,?,?,?,?,?,CAST(GETDATE() AS DATE),DATEADD(year,1,CAST(GETDATE() AS DATE)),1)""",
              (username, password_hash, fullname, role, available_card, email, phone), commit=True)
        print("Created account:", username, "| Mã thẻ:", available_card)

# Vô hiệu hóa tài khoản Quản trị viên mẫu cũ nếu đã được tạo trước đây.
# Không xóa bản ghi để tránh vi phạm khóa ngoại với phiếu mượn cũ.
query("""UPDATE NguoiDung SET TrangThaiTaiKhoan=0
         WHERE VaiTro=N'QuanTri' OR TenDangNhap=N'admin'""", commit=True)

staff = query("SELECT MaND FROM NguoiDung WHERE TenDangNhap=N'thuthu123'", one=True)
if not staff:
    raise RuntimeError("Không tìm thấy tài khoản thủ thư thuthu123.")
staff_id = staff["MaND"]

# -------------------- 2. THỂ LOẠI --------------------
category_names = [
    "Công nghệ thông tin", "Khoa học", "Văn học", "Kinh tế", "Lịch sử",
    "Ngoại ngữ", "Kỹ năng sống", "Toán học", "Tâm lý học", "Thiếu nhi"
]
for name in category_names:
    query("""IF NOT EXISTS (SELECT 1 FROM TheLoai WHERE TenTheLoai=?)
             INSERT INTO TheLoai(TenTheLoai) VALUES(?)""", (name, name), commit=True)
category_rows = query("SELECT MaTheLoai,TenTheLoai FROM TheLoai")
category_ids = {r["TenTheLoai"]: r["MaTheLoai"] for r in category_rows}

# -------------------- 3. ĐẦU SÁCH MẪU --------------------
books = [
    ("CNTT001", "Lập trình Python cơ bản", "Nguyễn Văn A", "NXB Giáo dục", 2023, "9786040010001", "Công nghệ thông tin"),
    ("CNTT002", "Cơ sở dữ liệu", "Trần Văn B", "NXB Khoa học", 2022, "9786040010002", "Công nghệ thông tin"),
    ("CNTT003", "Phân tích và thiết kế hệ thống", "Lê Minh C", "NXB Thông tin", 2021, "9786040010003", "Công nghệ thông tin"),
    ("CNTT004", "Mạng máy tính căn bản", "Phạm Văn D", "NXB Giáo dục", 2020, "9786040010004", "Công nghệ thông tin"),
    ("CNTT005", "Trí tuệ nhân tạo nhập môn", "Hoàng Văn E", "NXB Bách khoa", 2024, "9786040010005", "Công nghệ thông tin"),
    ("KHOA001", "Vũ trụ trong lòng bàn tay", "Nguyễn Nhật Ánh", "NXB Trẻ", 2021, "9786040010006", "Khoa học"),
    ("VANH001", "Cho tôi xin một vé đi tuổi thơ", "Nguyễn Nhật Ánh", "NXB Trẻ", 2019, "9786040010007", "Văn học"),
    ("VANH002", "Dế Mèn phiêu lưu ký", "Tô Hoài", "NXB Kim Đồng", 2020, "9786040010008", "Văn học"),
    ("VANH003", "Tắt đèn", "Ngô Tất Tố", "NXB Văn học", 2018, "9786040010009", "Văn học"),
    ("KT001", "Đắc nhân tâm", "Dale Carnegie", "NXB Tổng hợp", 2022, "9786040010010", "Kỹ năng sống"),
    ("KT002", "Nhà giả kim", "Paulo Coelho", "NXB Văn học", 2021, "9786040010011", "Văn học"),
    ("KT003", "Kinh tế học căn bản", "N. Gregory Mankiw", "NXB Kinh tế", 2020, "9786040010012", "Kinh tế"),
    ("LS001", "Lược sử Việt Nam", "Trần Trọng Kim", "NXB Văn hóa", 2019, "9786040010013", "Lịch sử"),
    ("NN001", "English Grammar in Use", "Raymond Murphy", "Cambridge", 2021, "9786040010014", "Ngoại ngữ"),
    ("TOAN001", "Đại số tuyến tính", "Nguyễn Đình Trí", "NXB Giáo dục", 2022, "9786040010015", "Toán học"),
    ("TL001", "Tâm lý học đại cương", "Bùi Văn Huệ", "NXB Đại học", 2020, "9786040010016", "Tâm lý học"),
    ("TN001", "Những câu chuyện tuổi thơ", "Nhiều tác giả", "NXB Kim Đồng", 2023, "9786040010017", "Thiếu nhi"),
]

for code, title, author, publisher, year, isbn, category in books:
    exists = query("SELECT MaSach FROM Sach WHERE MaDauSach=?", (code,), one=True)
    if not exists:
        query("""INSERT INTO Sach(MaDauSach,TenSach,TacGia,NhaXuatBan,NamXuatBan,ISBN,MaTheLoai,MoTa)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (code, title, author, publisher, year, isbn, category_ids.get(category),
               "Đầu sách mẫu được thêm sẵn để phục vụ kiểm thử hệ thống thư viện."), commit=True)
        print("Created book:", title)

# -------------------- 4. BẢN SAO SÁCH --------------------
book_rows = query("SELECT MaSach,MaDauSach FROM Sach WHERE MaDauSach LIKE N'CNTT%' OR MaDauSach IN (" + ",".join("?" for _ in books if not _[0].startswith("CNTT")) + ")", tuple(b[0] for b in books if not b[0].startswith("CNTT")))
for book in book_rows:
    for number in (1, 2, 3):
        barcode = f"{book['MaDauSach']}-C{number:02d}"
        query("""IF NOT EXISTS (SELECT 1 FROM CopySach WHERE MaVach=?)
                 INSERT INTO CopySach(MaSach,MaVach,ToaNha,Phong,Ke,Tang,GhiChu)
                 VALUES(?,?,N'Tòa A',N'Phòng thư viện',?,?,N'Bản sao dữ liệu mẫu')""",
              (barcode, book["MaSach"], barcode, f"Kệ {((number-1)%3)+1}", "Tầng 1"), commit=True)

# -------------------- 5. PHIẾU MƯỢN / TRẢ / PHẠT --------------------
reader_names = ["docgia", "docgia02", "docgia03", "docgia04", "docgia05"]
reader_ids = {}
for username in reader_names:
    row = query("SELECT MaND FROM NguoiDung WHERE TenDangNhap=?", (username,), one=True)
    reader_ids[username] = row["MaND"]

# Mỗi mã là một bộ dữ liệu mẫu riêng, tránh tạo trùng khi chạy lại.
today = date.today()
loan_samples = [
    ("M01", "docgia", "CNTT001-C01", today - timedelta(days=24), today - timedelta(days=10), "DangMuon", None),
    ("M02", "docgia02", "CNTT002-C01", today - timedelta(days=5), today + timedelta(days=9), "DangMuon", None),
    ("M03", "docgia03", "VANH001-C01", today - timedelta(days=25), today - timedelta(days=11), "DaTra", today - timedelta(days=7)),
    ("M04", "docgia04", "KT003-C01", today - timedelta(days=8), today + timedelta(days=6), "DangMuon", None),
    ("M05", "docgia05", "LS001-C01", today - timedelta(days=30), today - timedelta(days=16), "DaTra", today - timedelta(days=18)),
    ("M06", "docgia02", "NN001-C01", today - timedelta(days=4), today + timedelta(days=10), "DangMuon", None),
    ("M07", "docgia03", "CNTT003-C01", today - timedelta(days=20), today - timedelta(days=6), "DangMuon", None),
    ("M08", "docgia04", "VANH002-C01", today - timedelta(days=3), today + timedelta(days=11), "DangMuon", None),
]

for marker, reader_username, barcode, borrowed, due, detail_status, returned in loan_samples:
    marker_text = "DU_LIEU_MAU_" + marker
    exists = query("SELECT MaPhieuMuon FROM PhieuMuon WHERE GhiChu=?", (marker_text,), one=True)
    if exists:
        continue
    copy_row = query("SELECT MaCopy,TrangThai FROM CopySach WHERE MaVach=?", (barcode,), one=True)
    if not copy_row:
        print("Skipped loan, missing copy:", barcode)
        continue
    # Không ghi đè trạng thái của bản sao đang được sử dụng bởi dữ liệu thật.
    if copy_row["TrangThai"] not in ("CoSan", "DangMuon"):
        print("Skipped loan, copy unavailable:", barcode)
        continue
    query("""INSERT INTO PhieuMuon(MaDocGia,MaThuThu,NgayMuon,NgayHenTra,TrangThai,GhiChu)
             VALUES(?,?,?,?,?,?)""",
          (reader_ids[reader_username], staff_id, borrowed, due,
           "DaTra" if detail_status == "DaTra" else "DangMuon", marker_text), commit=True)
    loan = query("SELECT MaPhieuMuon FROM PhieuMuon WHERE GhiChu=?", (marker_text,), one=True)
    query("""INSERT INTO PhieuMuonDetail(MaPhieuMuon,MaCopy,NgayTraThucTe,TinhTrangTra,TrangThai)
             VALUES(?,?,?,?,?)""",
          (loan["MaPhieuMuon"], copy_row["MaCopy"], returned,
           "Tot" if returned else None, detail_status), commit=True)
    detail = query("SELECT MaCT FROM PhieuMuonDetail WHERE MaPhieuMuon=? AND MaCopy=?",
                   (loan["MaPhieuMuon"], copy_row["MaCopy"]), one=True)
    if detail_status == "DaTra":
        query("UPDATE CopySach SET TrangThai=N'CoSan' WHERE MaCopy=?", (copy_row["MaCopy"],), commit=True)
        late_days = max(0, (returned - due).days) if returned else 0
        if late_days:
            query("""INSERT INTO PhieuPhat(MaCT,SoNgayTre,DonGia,TongTien,TrangThaiThanhToan,GhiChu)
                     VALUES(?,?,?,?,N'DaThu',N'Khoản phạt dữ liệu mẫu')""",
                  (detail["MaCT"], late_days, 5000, late_days * 5000), commit=True)
    else:
        query("UPDATE CopySach SET TrangThai=N'DangMuon' WHERE MaCopy=?", (copy_row["MaCopy"],), commit=True)

# Tạo một yêu cầu gia hạn chờ duyệt cho một khoản đang mượn còn hạn.
renewal_detail = query("""SELECT TOP 1 d.MaCT,p.MaDocGia FROM PhieuMuonDetail d
                         JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                         WHERE p.GhiChu=N'DU_LIEU_MAU_M02' AND d.TrangThai=N'DangMuon'""", one=True)
if renewal_detail:
    query("""IF NOT EXISTS (SELECT 1 FROM PhieuGiaHan WHERE MaCT=? AND LyDo=N'Yêu cầu gia hạn mẫu')
             INSERT INTO PhieuGiaHan(MaCT,MaDocGia,SoNgayGiaHan,LyDo,TrangThai)
             VALUES(?,?,7,N'Yêu cầu gia hạn mẫu',N'ChoDuyet')""",
          (renewal_detail["MaCT"], renewal_detail["MaCT"], renewal_detail["MaDocGia"]), commit=True)

print("\nHoàn tất tạo dữ liệu mẫu thư viện.")
print("Thủ thư: thuthu123 / Giang@123")
print("Độc giả: docgia / DocGia@123")
print("Độc giả khác: docgia02 đến docgia05 / DocGia@123")

