/*
  Library Management System - SQL Server schema
  Run this script in SSMS using Windows Authentication.
  It creates LibraryDB if it does not already exist.
*/
IF DB_ID(N'LibraryDB_Complete') IS NULL
    CREATE DATABASE LibraryDB_Complete;
GO
USE LibraryDB_Complete;
GO

IF OBJECT_ID('dbo.PhieuGiaHan','U') IS NOT NULL DROP TABLE dbo.PhieuGiaHan;
IF OBJECT_ID('dbo.PhieuPhat','U') IS NOT NULL DROP TABLE dbo.PhieuPhat;
IF OBJECT_ID('dbo.PhieuMuonDetail','U') IS NOT NULL DROP TABLE dbo.PhieuMuonDetail;
IF OBJECT_ID('dbo.PhieuMuon','U') IS NOT NULL DROP TABLE dbo.PhieuMuon;
IF OBJECT_ID('dbo.CopySach','U') IS NOT NULL DROP TABLE dbo.CopySach;
IF OBJECT_ID('dbo.Sach','U') IS NOT NULL DROP TABLE dbo.Sach;
IF OBJECT_ID('dbo.TheLoai','U') IS NOT NULL DROP TABLE dbo.TheLoai;
IF OBJECT_ID('dbo.NguoiDung','U') IS NOT NULL DROP TABLE dbo.NguoiDung;
GO

CREATE TABLE dbo.NguoiDung (
    MaND INT IDENTITY(1,1) PRIMARY KEY,
    TenDangNhap NVARCHAR(50) NOT NULL UNIQUE,
    MatKhau NVARCHAR(255) NOT NULL,
    HoTen NVARCHAR(120) NOT NULL,
    Email NVARCHAR(120) NULL,
    SoDienThoai NVARCHAR(20) NULL,
    NgaySinh DATE NULL,
    DiaChi NVARCHAR(255) NULL,
    VaiTro NVARCHAR(20) NOT NULL CHECK (VaiTro IN (N'QuanTri',N'ThuThu',N'DocGia')),
    MaThe NVARCHAR(30) NULL,
    NgayCapThe DATE NULL,
    NgayHetHan DATE NULL,
    TrangThaiThe NVARCHAR(20) NOT NULL DEFAULT N'HoatDong',
    TrangThaiTaiKhoan BIT NOT NULL DEFAULT 1,
    NgayTao DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE dbo.TheLoai (
    MaTheLoai INT IDENTITY(1,1) PRIMARY KEY,
    TenTheLoai NVARCHAR(100) NOT NULL UNIQUE,
    MaTheLoaiCha INT NULL REFERENCES dbo.TheLoai(MaTheLoai)
);
GO

CREATE TABLE dbo.Sach (
    MaSach INT IDENTITY(1,1) PRIMARY KEY,
    MaDauSach NVARCHAR(30) NOT NULL UNIQUE,
    TenSach NVARCHAR(200) NOT NULL,
    TacGia NVARCHAR(150) NOT NULL,
    NhaXuatBan NVARCHAR(150) NULL,
    NamXuatBan INT NULL,
    ISBN NVARCHAR(30) NULL,
    MaTheLoai INT NULL REFERENCES dbo.TheLoai(MaTheLoai),
    MoTa NVARCHAR(1000) NULL,
    TrangThai NVARCHAR(20) NOT NULL DEFAULT N'DangSuDung',
    NgayTao DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE TABLE dbo.CopySach (
    MaCopy INT IDENTITY(1,1) PRIMARY KEY,
    MaSach INT NOT NULL REFERENCES dbo.Sach(MaSach),
    MaVach NVARCHAR(40) NOT NULL UNIQUE,
    ToaNha NVARCHAR(80) NULL,
    Phong NVARCHAR(80) NULL,
    Ke NVARCHAR(40) NULL,
    Tang NVARCHAR(20) NULL,
    TrangThai NVARCHAR(20) NOT NULL DEFAULT N'CoSan'
        CHECK (TrangThai IN (N'CoSan',N'DangMuon',N'DaThanhLy',N'DatTruoc')),
    GhiChu NVARCHAR(300) NULL
);
GO

CREATE TABLE dbo.PhieuMuon (
    MaPhieuMuon INT IDENTITY(1,1) PRIMARY KEY,
    MaDocGia INT NOT NULL REFERENCES dbo.NguoiDung(MaND),
    MaThuThu INT NOT NULL REFERENCES dbo.NguoiDung(MaND),
    NgayMuon DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    NgayHenTra DATE NOT NULL,
    TrangThai NVARCHAR(20) NOT NULL DEFAULT N'DangMuon',
    GhiChu NVARCHAR(500) NULL
);
GO

CREATE TABLE dbo.PhieuMuonDetail (
    MaCT INT IDENTITY(1,1) PRIMARY KEY,
    MaPhieuMuon INT NOT NULL REFERENCES dbo.PhieuMuon(MaPhieuMuon),
    MaCopy INT NOT NULL REFERENCES dbo.CopySach(MaCopy),
    NgayTraThucTe DATE NULL,
    TinhTrangTra NVARCHAR(30) NULL,
    TrangThai NVARCHAR(20) NOT NULL DEFAULT N'DangMuon'
);
GO

CREATE TABLE dbo.PhieuPhat (
    MaPhieuPhat INT IDENTITY(1,1) PRIMARY KEY,
    MaCT INT NOT NULL REFERENCES dbo.PhieuMuonDetail(MaCT),
    SoNgayTre INT NOT NULL,
    DonGia DECIMAL(12,2) NOT NULL,
    TongTien DECIMAL(12,2) NOT NULL,
    HinhThuc NVARCHAR(30) NULL,
    TrangThaiThanhToan NVARCHAR(20) NOT NULL DEFAULT N'ChuaThu',
    NgayThu DATETIME2 NULL,
    GhiChu NVARCHAR(300) NULL
);
GO

CREATE TABLE dbo.PhieuGiaHan (
    MaYeuCau INT IDENTITY(1,1) PRIMARY KEY,
    MaCT INT NOT NULL REFERENCES dbo.PhieuMuonDetail(MaCT),
    MaDocGia INT NOT NULL REFERENCES dbo.NguoiDung(MaND),
    SoNgayGiaHan INT NOT NULL,
    LyDo NVARCHAR(500) NOT NULL,
    TrangThai NVARCHAR(20) NOT NULL DEFAULT N'ChoDuyet',
    NgayGui DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    MaThuThuDuyet INT NULL REFERENCES dbo.NguoiDung(MaND),
    NgayDuyet DATETIME2 NULL
);
GO

CREATE UNIQUE INDEX UX_NguoiDung_MaThe ON dbo.NguoiDung(MaThe) WHERE MaThe IS NOT NULL;
CREATE UNIQUE INDEX UX_Sach_ISBN ON dbo.Sach(ISBN) WHERE ISBN IS NOT NULL;
CREATE INDEX IX_Sach_TenSach ON dbo.Sach(TenSach);
CREATE INDEX IX_PhieuMuon_MaDocGia ON dbo.PhieuMuon(MaDocGia);
CREATE INDEX IX_PhieuMuonDetail_TrangThai ON dbo.PhieuMuonDetail(TrangThai);
GO

INSERT INTO dbo.TheLoai(TenTheLoai) VALUES
(N'Công nghệ thông tin'),(N'Khoa học'),(N'Văn học'),(N'Kinh tế'),(N'Lịch sử');
GO
