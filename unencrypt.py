import pyodbc
from cryptography.fernet import Fernet

# Đọc khóa mã hóa từ tệp để giải mã
with open('encryption_key.key', 'rb') as key_file:
    key = key_file.read()

cipher_suite = Fernet(key)

# Kết nối tới SQL Server
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER= Hacker303;'
    'DATABASE=QuanLyDiemDanh;'
    'Trusted_Connection=yes;')
cursor = conn.cursor()
#msv
select_query = '''
    SELECT FolderAnh 
    FROM SinhVien 
    WHERE MaSinhVien = ?
'''
cursor.execute(select_query, (ma_sinh_vien,))

# Lấy dữ liệu mã hóa
row = cursor.fetchone()
if row:
    encrypted_data = row[0]  # FolderAnh chứa dữ liệu đã mã hóa
else:
    print(f"Không tìm thấy sinh viên với MaSinhVien: {ma_sinh_vien}")

cursor.close()
conn.close()

# Giải mã dữ liệu
if encrypted_data:
    decrypted_data = cipher_suite.decrypt(encrypted_data)

    # Lưu tệp zip đã giải mã ra ổ đĩa
    zip_filename = f'{ma_sinh_vien}_folder.zip'
    with open(zip_filename, 'wb') as zip_file:
        zip_file.write(decrypted_data)

    # Giải nén tệp zip
    import zipfile
    with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
        zip_ref.extractall(f'output/{ma_sinh_vien}_folder')

    print(f"Đã giải mã và giải nén thư mục cho MaSinhVien: {ma_sinh_vien}")
