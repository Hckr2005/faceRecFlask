import pyodbc

from encrypt import encrypted_folders

# Kết nối đến SQL Server
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER= Hacker303;'
    'DATABASE=QuanLyDiemDanh;'
    'Trusted_Connection=yes;')
cursor = conn.cursor()

# Câu lệnh SQL để lưu tệp mã hóa vào bảng
update_query = '''
    UPDATE SinhVien
    SET FolderAnh = ?
    WHERE MaSinhVien = ?
'''

# Đẩy từng thư mục lên SQL Server
for person_id, encrypted_data in encrypted_folders:
    cursor.execute(update_query, (encrypted_data, person_id))

conn.commit()

# Đóng kết nối
cursor.close()
conn.close()
