import os
import csv
import io
from datetime import date, datetime, timedelta
from functools import wraps

import pyodbc
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "please-change-this-secret")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

def db_connection():
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("DB_SERVER", r"(LOCAL)\SQLEXPRESS")
    database = os.getenv("DB_NAME", "LibraryDB_Complete")
    trusted = os.getenv("DB_TRUSTED_CONNECTION", "yes").lower() in ("yes", "true", "1")
    encrypt = os.getenv("DB_ENCRYPT", "no")
    trust_cert = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")
    parts = [
        f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}",
        f"Encrypt={encrypt}", f"TrustServerCertificate={trust_cert}"
    ]
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={os.getenv('DB_USER','')}", f"PWD={os.getenv('DB_PASSWORD','')}"])
    return pyodbc.connect(";".join(parts) + ";", timeout=5)

def query(sql, params=(), one=False, commit=False):
    conn = db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if commit:
            conn.commit()
            return cur.rowcount
        names = [c[0] for c in cur.description] if cur.description else []
        rows = [dict(zip(names, row)) for row in cur.fetchall()] if names else []
        return (rows[0] if rows else None) if one else rows
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()

def current_user():
    return session.get("user")

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user()["role"] not in roles:
                flash("Bạn không có quyền truy cập chức năng này.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco

def setting(name, default):
    return int(os.getenv(name, default))

@app.context_processor
def inject_globals():
    return {"me": current_user(), "today": date.today()}

@app.route("/")
def home():
    return redirect(url_for("dashboard") if current_user() else url_for("catalog"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("""SELECT MaND,TenDangNhap,MatKhau,HoTen,VaiTro,TrangThaiTaiKhoan,TrangThaiThe
                        FROM NguoiDung WHERE TenDangNhap=?""", (username,), one=True)
        if (not user or user["VaiTro"] not in ("ThuThu", "DocGia")
                or not user["TrangThaiTaiKhoan"]
                or not check_password_hash(user["MatKhau"], password)):
            flash("Tên đăng nhập hoặc mật khẩu không chính xác.", "danger")
        elif user["VaiTro"] == "DocGia" and user["TrangThaiThe"] == "Khoa":
            flash("Thẻ độc giả đang bị khóa. Vui lòng liên hệ thủ thư.", "danger")
        else:
            session.clear()
            session["user"] = {"id": user["MaND"], "username": user["TenDangNhap"],
                               "name": user["HoTen"], "role": user["VaiTro"]}
            session.permanent = True
            return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "success")
    return redirect(url_for("login"))

@app.route("/catalog")
def catalog():
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    sql = """SELECT s.MaSach,s.MaDauSach,s.TenSach,s.TacGia,s.NhaXuatBan,s.NamXuatBan,
                    t.TenTheLoai,
                    COUNT(CASE WHEN c.TrangThai=N'CoSan' THEN 1 END) AS SoLuongCon,
                    COUNT(c.MaCopy) AS TongSoLuong,
                    MIN(c.ToaNha) AS ToaNha, MIN(c.Phong) AS Phong, MIN(c.Ke) AS Ke, MIN(c.Tang) AS Tang
             FROM Sach s LEFT JOIN TheLoai t ON s.MaTheLoai=t.MaTheLoai
             LEFT JOIN CopySach c ON s.MaSach=c.MaSach
             WHERE s.TrangThai=N'DangSuDung'
               AND (?=N'' OR s.TenSach LIKE N'%'+?+N'%' OR s.TacGia LIKE N'%'+?+N'%')
               AND (?=N'' OR CAST(s.MaTheLoai AS NVARCHAR(20))=?)
             GROUP BY s.MaSach,s.MaDauSach,s.TenSach,s.TacGia,s.NhaXuatBan,s.NamXuatBan,t.TenTheLoai
             ORDER BY s.TenSach"""
    books = query(sql, (keyword, keyword, keyword, category, category))
    categories = query("SELECT MaTheLoai,TenTheLoai FROM TheLoai ORDER BY TenTheLoai")
    return render_template("catalog.html", books=books, categories=categories, q=keyword, category=category)

@app.route("/dashboard")
@login_required
def dashboard():
    stats = query("""SELECT
       (SELECT COUNT(*) FROM Sach WHERE TrangThai=N'DangSuDung') AS DauSach,
       (SELECT COUNT(*) FROM CopySach WHERE TrangThai=N'CoSan') AS SachCoSan,
       (SELECT COUNT(*) FROM PhieuMuonDetail WHERE TrangThai=N'DangMuon') AS DangMuon,
       (SELECT COUNT(*) FROM PhieuPhat WHERE TrangThaiThanhToan=N'ChuaThu') AS KhoanChuaThu""", one=True)
    overdue = query("""SELECT COUNT(*) AS SoLuong FROM PhieuMuonDetail d
        JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
        WHERE d.TrangThai=N'DangMuon' AND p.NgayHenTra<CAST(GETDATE() AS DATE)""", one=True)
    return render_template("dashboard.html", stats=stats, overdue=overdue["SoLuong"])

@app.route("/books", methods=["GET", "POST"])
@roles_required("ThuThu")
def books():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "save":
                code = request.form["code"].strip()
                title = request.form["title"].strip()
                author = request.form["author"].strip()
                isbn = request.form.get("isbn", "").strip() or None
                year = request.form.get("year") or None
                category = request.form.get("category") or None
                publisher = request.form.get("publisher", "").strip()
                desc = request.form.get("description", "").strip()
                book_id = request.form.get("book_id")
                if not code or not title or not author:
                    raise ValueError("Mã đầu sách, tên sách và tác giả là bắt buộc.")
                if year and (int(year) < 0 or int(year) > date.today().year):
                    raise ValueError("Năm xuất bản không hợp lệ.")
                if book_id:
                    query("""UPDATE Sach SET TenSach=?,TacGia=?,NhaXuatBan=?,NamXuatBan=?,
                             ISBN=?,MaTheLoai=?,MoTa=? WHERE MaSach=?""",
                          (title, author, publisher, year, isbn, category, desc, book_id), commit=True)
                    flash("Đã cập nhật thông tin sách.", "success")
                else:
                    query("""INSERT INTO Sach(MaDauSach,TenSach,TacGia,NhaXuatBan,NamXuatBan,ISBN,MaTheLoai,MoTa)
                              VALUES(?,?,?,?,?,?,?,?)""",
                          (code, title, author, publisher, year, isbn, category, desc), commit=True)
                    flash("Đã thêm đầu sách. Tiếp theo hãy thêm từng bản sao/mã vạch trong danh sách sách.", "success")
            elif action == "copy":
                query("""INSERT INTO CopySach(MaSach,MaVach,ToaNha,Phong,Ke,Tang)
                          VALUES(?,?,?,?,?,?)""",
                      (request.form["copy_book"], request.form["barcode"].strip(),
                       request.form.get("building"), request.form.get("room"),
                       request.form.get("shelf"), request.form.get("floor")), commit=True)
                flash("Đã thêm bản sao sách.", "success")
            elif action == "category":
                category_name = request.form.get("category_name", "").strip()
                if not category_name:
                    raise ValueError("Tên thể loại không được để trống.")
                query("INSERT INTO TheLoai(TenTheLoai) VALUES(?)", (category_name,), commit=True)
                flash("Đã thêm thể loại sách.", "success")
            elif action == "archive":
                book_id = request.form["book_id"]
                reason = request.form.get("reason", "").strip()
                if not reason:
                    raise ValueError("Cần nhập lý do thanh lý.")
                active = query("""SELECT COUNT(*) AS n FROM CopySach c JOIN PhieuMuonDetail d ON c.MaCopy=d.MaCopy
                                  WHERE c.MaSach=? AND d.TrangThai=N'DangMuon'""", (book_id,), one=True)
                if active["n"]:
                    raise ValueError("Không thể thanh lý sách đang được mượn.")
                query("UPDATE Sach SET TrangThai=N'DaThanhLy',MoTa=CONCAT(ISNULL(MoTa,N''),N' | Lý do thanh lý: ',?) WHERE MaSach=?",
                      (reason, book_id), commit=True)
                query("UPDATE CopySach SET TrangThai=N'DaThanhLy' WHERE MaSach=? AND TrangThai=N'CoSan'",
                      (book_id,), commit=True)
                flash("Đã chuyển hồ sơ sách sang trạng thái thanh lý.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Không thể lưu dữ liệu. Kiểm tra mã sách/ISBN/mã vạch có bị trùng không. Chi tiết: " + str(e), "danger")
        return redirect(url_for("books"))
    books_data = query("""SELECT s.*,t.TenTheLoai,
        COUNT(c.MaCopy) AS TongBanSao,
        SUM(CASE WHEN c.TrangThai=N'CoSan' THEN 1 ELSE 0 END) AS ConSan
        FROM Sach s LEFT JOIN TheLoai t ON s.MaTheLoai=t.MaTheLoai
        LEFT JOIN CopySach c ON s.MaSach=c.MaSach
        WHERE s.TrangThai=N'DangSuDung'
        GROUP BY s.MaSach,s.MaDauSach,s.TenSach,s.TacGia,s.NhaXuatBan,s.NamXuatBan,s.ISBN,s.MaTheLoai,s.MoTa,s.TrangThai,s.NgayTao,t.TenTheLoai
        ORDER BY s.MaSach DESC""")
    copies = query("""SELECT c.*,s.TenSach FROM CopySach c JOIN Sach s ON c.MaSach=s.MaSach
                      WHERE c.TrangThai<>N'DaThanhLy' ORDER BY c.MaCopy DESC""")
    categories = query("SELECT * FROM TheLoai ORDER BY TenTheLoai")
    return render_template("books.html", books=books_data, copies=copies, categories=categories)

@app.route("/readers", methods=["GET", "POST"])
@roles_required("ThuThu")
def readers():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "save":
                name=request.form["name"].strip()
                username=request.form["username"].strip()
                card=request.form["card"].strip()
                email=request.form.get("email","").strip()
                phone=request.form.get("phone","").strip()
                expiry=request.form["expiry"]
                reader_id=request.form.get("reader_id")
                if not name or not username or not card:
                    raise ValueError("Họ tên, tên đăng nhập và mã thẻ là bắt buộc.")
                if phone and (not phone.isdigit() or len(phone) not in (10,11)):
                    raise ValueError("Số điện thoại cần có 10 hoặc 11 chữ số.")
                if reader_id:
                    query("""UPDATE NguoiDung SET HoTen=?,Email=?,SoDienThoai=?,NgayHetHan=? WHERE MaND=? AND VaiTro=N'DocGia'""",
                          (name,email,phone,expiry,reader_id),commit=True)
                else:
                    password=generate_password_hash(request.form.get("password") or "Reader@123")
                    query("""INSERT INTO NguoiDung(TenDangNhap,MatKhau,HoTen,Email,SoDienThoai,VaiTro,MaThe,NgayCapThe,NgayHetHan)
                              VALUES(?,?,?,?,?,N'DocGia',?,CAST(GETDATE() AS DATE),?)""",
                          (username,password,name,email,phone,card,expiry),commit=True)
                flash("Đã lưu hồ sơ độc giả.", "success")
            elif action in ("lock","unlock"):
                rid=request.form["reader_id"]
                state="Khoa" if action=="lock" else "HoatDong"
                query("UPDATE NguoiDung SET TrangThaiThe=? WHERE MaND=? AND VaiTro=N'DocGia'",(state,rid),commit=True)
                flash("Đã cập nhật trạng thái thẻ.", "success")
        except Exception as e:
            flash("Không thể lưu độc giả: " + str(e), "danger")
        return redirect(url_for("readers"))
    data=query("""SELECT MaND,TenDangNhap,HoTen,Email,SoDienThoai,MaThe,NgayCapThe,NgayHetHan,TrangThaiThe
                  FROM NguoiDung WHERE VaiTro=N'DocGia' ORDER BY MaND DESC""")
    return render_template("readers.html", readers=data)

@app.route("/loans", methods=["GET","POST"])
@roles_required("ThuThu")
def loans():
    if request.method=="POST":
        try:
            reader=query("SELECT * FROM NguoiDung WHERE MaThe=? AND VaiTro=N'DocGia'",(request.form["card"].strip(),),one=True)
            if not reader: raise ValueError("Không tìm thấy thẻ độc giả.")
            if reader["TrangThaiThe"]!="HoatDong" or (reader["NgayHetHan"] and reader["NgayHetHan"]<date.today()):
                raise ValueError("Thẻ độc giả đã khóa hoặc hết hạn.")
            debt=query("""SELECT COUNT(*) AS n FROM PhieuMuonDetail d JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                          WHERE p.MaDocGia=? AND d.TrangThai=N'DangMuon' AND p.NgayHenTra<CAST(GETDATE() AS DATE)""",
                       (reader["MaND"],),one=True)
            unpaid=query("""SELECT COUNT(*) AS n FROM PhieuPhat f JOIN PhieuMuonDetail d ON f.MaCT=d.MaCT
                            JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                            WHERE p.MaDocGia=? AND f.TrangThaiThanhToan=N'ChuaThu'""",(reader["MaND"],),one=True)
            active=query("""SELECT COUNT(*) AS n FROM PhieuMuonDetail d JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                            WHERE p.MaDocGia=? AND d.TrangThai=N'DangMuon'""",(reader["MaND"],),one=True)
            if debt["n"] or unpaid["n"]: raise ValueError("Độc giả còn sách quá hạn hoặc tiền phạt chưa thanh toán.")
            if active["n"] >= setting("MAX_BOOKS_PER_READER",5): raise ValueError("Độc giả đã đạt giới hạn sách được mượn.")
            copy=query("""SELECT c.MaCopy FROM CopySach c WHERE c.MaVach=? AND c.TrangThai=N'CoSan'""",
                       (request.form["barcode"].strip(),),one=True)
            if not copy: raise ValueError("Mã vạch không tồn tại hoặc sách không còn sẵn.")
            loan_date=date.today()
            due=loan_date+timedelta(days=setting("LOAN_DAYS",14))
            conn=db_connection()
            try:
                cur=conn.cursor()
                cur.execute("""INSERT INTO PhieuMuon(MaDocGia,MaThuThu,NgayMuon,NgayHenTra)
                               OUTPUT INSERTED.MaPhieuMuon VALUES(?,?,?,?)""",
                            (reader["MaND"],current_user()["id"],loan_date,due))
                loan_id=cur.fetchone()[0]
                cur.execute("INSERT INTO PhieuMuonDetail(MaPhieuMuon,MaCopy) VALUES(?,?)",(loan_id,copy["MaCopy"]))
                cur.execute("UPDATE CopySach SET TrangThai=N'DangMuon' WHERE MaCopy=?",(copy["MaCopy"],))
                conn.commit()
            finally: conn.close()
            flash(f"Đã lập phiếu mượn #{loan_id}. Hạn trả: {due.strftime('%d/%m/%Y')}.","success")
        except ValueError as e: flash(str(e),"danger")
        except Exception as e: flash("Lỗi lập phiếu mượn: "+str(e),"danger")
        return redirect(url_for("loans"))
    data=query("""SELECT p.MaPhieuMuon,p.NgayMuon,p.NgayHenTra,p.TrangThai,
                  nd.HoTen AS DocGia,nd.MaThe,s.TenSach,c.MaVach,d.MaCT,d.TrangThai AS TrangThaiCT
                  FROM PhieuMuon p JOIN NguoiDung nd ON p.MaDocGia=nd.MaND
                  JOIN PhieuMuonDetail d ON p.MaPhieuMuon=d.MaPhieuMuon
                  JOIN CopySach c ON d.MaCopy=c.MaCopy JOIN Sach s ON c.MaSach=s.MaSach
                  ORDER BY p.MaPhieuMuon DESC""")
    return render_template("loans.html", loans=data)

@app.route("/return/<int:detail_id>", methods=["POST"])
@roles_required("ThuThu")
def return_book(detail_id):
    try:
        row=query("""SELECT d.MaCT,d.MaCopy,d.TrangThai,p.NgayHenTra
                     FROM PhieuMuonDetail d JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                     WHERE d.MaCT=?""",(detail_id,),one=True)
        if not row or row["TrangThai"]!="DangMuon": raise ValueError("Chi tiết mượn không tồn tại hoặc đã trả.")
        returned=date.today()
        late=max(0,(returned-row["NgayHenTra"]).days)
        fine_rate=setting("FINE_PER_DAY",5000)
        conn=db_connection()
        try:
            cur=conn.cursor()
            cur.execute("""UPDATE PhieuMuonDetail SET NgayTraThucTe=?,TinhTrangTra=?,TrangThai=N'DaTra'
                           WHERE MaCT=?""",(returned,request.form.get("condition","Tot"),detail_id))
            cur.execute("UPDATE CopySach SET TrangThai=N'CoSan' WHERE MaCopy=?",(row["MaCopy"],))
            if late:
                cur.execute("""INSERT INTO PhieuPhat(MaCT,SoNgayTre,DonGia,TongTien)
                               VALUES(?,?,?,?)""",(detail_id,late,fine_rate,late*fine_rate))
            conn.commit()
        finally: conn.close()
        flash("Đã ghi nhận trả sách."+(f" Tiền phạt quá hạn: {late*fine_rate:,.0f} VNĐ." if late else ""),"success")
    except Exception as e: flash("Không thể trả sách: "+str(e),"danger")
    return redirect(url_for("loans"))

@app.route("/extensions", methods=["GET","POST"])
@login_required
def extensions():
    if request.method=="POST":
        action=request.form.get("action")
        try:
            if action=="request":
                detail_id=request.form["detail_id"]
                days=int(request.form["days"])
                reason=request.form.get("reason","").strip()
                if days<1 or days>14 or not reason: raise ValueError("Số ngày gia hạn từ 1–14 và lý do không được để trống.")
                detail=query("""SELECT d.MaCT,d.TrangThai,p.MaDocGia,p.NgayHenTra,c.MaCopy
                                FROM PhieuMuonDetail d JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                                JOIN CopySach c ON d.MaCopy=c.MaCopy WHERE d.MaCT=?""",(detail_id,),one=True)
                if not detail or detail["TrangThai"]!="DangMuon": raise ValueError("Khoản mượn không hợp lệ.")
                if current_user()["role"]=="DocGia" and detail["MaDocGia"]!=current_user()["id"]:
                    raise ValueError("Bạn không thể gia hạn sách của người khác.")
                if detail["NgayHenTra"]<date.today(): raise ValueError("Không thể gửi yêu cầu gia hạn khi sách đã quá hạn.")
                count=query("SELECT COUNT(*) AS n FROM PhieuGiaHan WHERE MaCT=? AND TrangThai=N'DaDuyet'",(detail_id,),one=True)["n"]
                if count>=setting("MAX_EXTENSIONS",2): raise ValueError("Đã vượt số lần gia hạn tối đa.")
                query("""INSERT INTO PhieuGiaHan(MaCT,MaDocGia,SoNgayGiaHan,LyDo)
                          VALUES(?,?,?,?)""",(detail_id,detail["MaDocGia"],days,reason),commit=True)
                flash("Đã gửi yêu cầu gia hạn, vui lòng chờ thủ thư duyệt.","success")
            elif action in ("approve","reject") and current_user()["role"] == "ThuThu":
                req=query("""SELECT g.*,d.MaPhieuMuon,p.NgayHenTra,c.MaCopy
                             FROM PhieuGiaHan g JOIN PhieuMuonDetail d ON g.MaCT=d.MaCT
                             JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                             JOIN CopySach c ON d.MaCopy=c.MaCopy WHERE g.MaYeuCau=?""",
                          (request.form["request_id"],),one=True)
                if not req or req["TrangThai"]!="ChoDuyet": raise ValueError("Yêu cầu không còn ở trạng thái chờ duyệt.")
                if action=="approve":
                    reserved=query("SELECT COUNT(*) AS n FROM CopySach WHERE MaCopy=? AND TrangThai=N'DatTruoc'",(req["MaCopy"],),one=True)["n"]
                    if reserved: raise ValueError("Không thể duyệt vì sách đã được đặt trước.")
                    new_due=req["NgayHenTra"]+timedelta(days=req["SoNgayGiaHan"])
                    conn=db_connection()
                    try:
                        cur=conn.cursor()
                        cur.execute("UPDATE PhieuMuon SET NgayHenTra=? WHERE MaPhieuMuon=?",(new_due,req["MaPhieuMuon"]))
                        cur.execute("""UPDATE PhieuGiaHan SET TrangThai=N'DaDuyet',MaThuThuDuyet=?,NgayDuyet=SYSDATETIME()
                                       WHERE MaYeuCau=?""",(current_user()["id"],req["MaYeuCau"]))
                        conn.commit()
                    finally: conn.close()
                else:
                    query("""UPDATE PhieuGiaHan SET TrangThai=N'TuChoi',MaThuThuDuyet=?,NgayDuyet=SYSDATETIME()
                             WHERE MaYeuCau=?""",(current_user()["id"],req["MaYeuCau"]),commit=True)
                flash("Đã xử lý yêu cầu gia hạn.","success")
        except Exception as e: flash("Không thể xử lý yêu cầu: "+str(e),"danger")
        return redirect(url_for("extensions"))
    if current_user()["role"] == "ThuThu":
        data=query("""SELECT g.*,nd.HoTen,d.MaCT,s.TenSach,nd.MaThe
                      FROM PhieuGiaHan g JOIN NguoiDung nd ON g.MaDocGia=nd.MaND
                      JOIN PhieuMuonDetail d ON g.MaCT=d.MaCT JOIN CopySach c ON d.MaCopy=c.MaCopy
                      JOIN Sach s ON c.MaSach=s.MaSach ORDER BY g.NgayGui DESC""")
    else:
        data=query("""SELECT g.*,nd.HoTen,d.MaCT,s.TenSach,nd.MaThe
                      FROM PhieuGiaHan g JOIN NguoiDung nd ON g.MaDocGia=nd.MaND
                      JOIN PhieuMuonDetail d ON g.MaCT=d.MaCT JOIN CopySach c ON d.MaCopy=c.MaCopy
                      JOIN Sach s ON c.MaSach=s.MaSach
                      WHERE g.MaDocGia=? ORDER BY g.NgayGui DESC""",(current_user()["id"],))
    return render_template("extensions.html", requests=data)

@app.route("/my-account")
@roles_required("DocGia")
def my_account():
    loans=query("""SELECT p.MaPhieuMuon,p.NgayMuon,p.NgayHenTra,d.MaCT,d.NgayTraThucTe,d.TrangThai,
                   s.TenSach,c.MaVach,
                   CASE WHEN d.TrangThai=N'DangMuon' AND p.NgayHenTra<CAST(GETDATE() AS DATE)
                        THEN DATEDIFF(day,p.NgayHenTra,CAST(GETDATE() AS DATE)) ELSE 0 END AS SoNgayTre
                   FROM PhieuMuon p JOIN PhieuMuonDetail d ON p.MaPhieuMuon=d.MaPhieuMuon
                   JOIN CopySach c ON d.MaCopy=c.MaCopy JOIN Sach s ON c.MaSach=s.MaSach
                   WHERE p.MaDocGia=? ORDER BY p.MaPhieuMuon DESC""",(current_user()["id"],))
    return render_template("my_account.html", loans=loans)

@app.route("/reports")
@roles_required("ThuThu")
def reports():
    top=query("""SELECT TOP 10 s.TenSach,COUNT(*) AS LuotMuon
                 FROM PhieuMuonDetail d JOIN CopySach c ON d.MaCopy=c.MaCopy
                 JOIN Sach s ON c.MaSach=s.MaSach GROUP BY s.TenSach ORDER BY COUNT(*) DESC""")
    overdue=query("""SELECT nd.HoTen,nd.SoDienThoai,nd.MaThe,s.TenSach,p.NgayHenTra,
                     DATEDIFF(day,p.NgayHenTra,CAST(GETDATE() AS DATE)) AS SoNgayTre
                     FROM PhieuMuonDetail d JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon
                     JOIN NguoiDung nd ON p.MaDocGia=nd.MaND JOIN CopySach c ON d.MaCopy=c.MaCopy
                     JOIN Sach s ON c.MaSach=s.MaSach
                     WHERE d.TrangThai=N'DangMuon' AND p.NgayHenTra<CAST(GETDATE() AS DATE)
                     ORDER BY p.NgayHenTra""")
    fines=query("""SELECT ISNULL(SUM(TongTien),0) AS TongTien,
                   ISNULL(SUM(CASE WHEN TrangThaiThanhToan=N'DaThu' THEN TongTien ELSE 0 END),0) AS DaThu,
                   ISNULL(SUM(CASE WHEN TrangThaiThanhToan=N'ChuaThu' THEN TongTien ELSE 0 END),0) AS ChuaThu
                   FROM PhieuPhat""",one=True)
    fine_rows=query("""SELECT f.MaPhieuPhat,nd.HoTen,s.TenSach,f.SoNgayTre,f.DonGia,f.TongTien,
                       f.TrangThaiThanhToan FROM PhieuPhat f JOIN PhieuMuonDetail d ON f.MaCT=d.MaCT
                       JOIN PhieuMuon p ON d.MaPhieuMuon=p.MaPhieuMuon JOIN NguoiDung nd ON p.MaDocGia=nd.MaND
                       JOIN CopySach c ON d.MaCopy=c.MaCopy JOIN Sach s ON c.MaSach=s.MaSach
                       ORDER BY f.MaPhieuPhat DESC""")
    return render_template("reports.html",top=top,overdue=overdue,fines=fines,fine_rows=fine_rows)

@app.route("/fines/<int:fine_id>/collect", methods=["POST"])
@roles_required("ThuThu")
def collect_fine(fine_id):
    query("""UPDATE PhieuPhat SET TrangThaiThanhToan=N'DaThu',HinhThuc=?,NgayThu=SYSDATETIME()
             WHERE MaPhieuPhat=? AND TrangThaiThanhToan=N'ChuaThu'""",
          (request.form.get("method","TienMat"),fine_id),commit=True)
    flash("Đã ghi nhận thu tiền phạt.","success")
    return redirect(url_for("reports"))

@app.route("/users", methods=["GET","POST"])
@roles_required("ThuThu")
def users():
    if request.method=="POST":
        try:
            role=request.form["role"]
            if role not in ("ThuThu","DocGia"): raise ValueError("Chỉ được tạo tài khoản Thủ thư hoặc Độc giả.")
            password=generate_password_hash(request.form["password"])
            query("""INSERT INTO NguoiDung(TenDangNhap,MatKhau,HoTen,Email,VaiTro,MaThe,NgayCapThe,NgayHetHan)
                      VALUES(?,?,?,?,?,?,CAST(GETDATE() AS DATE),DATEADD(year,1,CAST(GETDATE() AS DATE)))""",
                  (request.form["username"].strip(),password,request.form["name"].strip(),
                   request.form.get("email","").strip(),role,
                   request.form.get("card") or None),commit=True)
            flash("Đã tạo tài khoản.","success")
        except Exception as e: flash("Không thể tạo tài khoản: "+str(e),"danger")
        return redirect(url_for("users"))
    data=query("SELECT MaND,TenDangNhap,HoTen,Email,VaiTro,TrangThaiTaiKhoan FROM NguoiDung ORDER BY MaND DESC")
    return render_template("users.html",users=data)

@app.errorhandler(pyodbc.Error)
def database_error(error):
    app.logger.exception("Database error")
    return render_template("error.html", message="Không kết nối được SQL Server. Hãy kiểm tra SQL Server đang chạy, tên instance trong .env, ODBC Driver 18 và database LibraryDB_Complete đã được tạo."), 500

if __name__ == "__main__":
    app.run(debug=True)
