import pyodbc
from cryptography.fernet import Fernet
import os
import zipfile


# Đọc khóa mã hóa từ tệp để giải mã
with open('encryption_key.key', 'rb') as key_file:
    key = key_file.read()

cipher_suite = Fernet(key)

# Truy vấn MaSinhVien, TenSinhVien và dữ liệu mã hóa FolderAnh
select_query = '''
    SELECT MaSinhVien, TenSinhVien, FolderAnh 
    FROM SinhVien
'''
cursor.execute(select_query)

# Lưu tất cả dữ liệu mã hóa vào danh sách
encrypted_folders = cursor.fetchall()


cursor.close()
conn.close()

local_face_directory = 'face'

# Giải mã và giải nén từng thư mục từ cơ sở dữ liệu
for row in encrypted_folders:
    ma_sinh_vien = row[0]  # MaSinhVien
    ten_sinh_vien = row[1]  # TenSinhVien
    encrypted_data = row[2]  # Dữ liệu mã hóa của FolderAnh

    if encrypted_data:
        # Giải mã dữ liệu
        decrypted_data = cipher_suite.decrypt(encrypted_data)

        # Tạo đường dẫn file zip tạm để lưu tệp đã giải mã
        zip_filename = f'{ma_sinh_vien}_folder.zip'
        with open(zip_filename, 'wb') as zip_file:
            zip_file.write(decrypted_data)

        # Đường dẫn tới folder sinh viên cục bộ theo định dạng TenSinhVien_MaSinhVien
        student_folder_name = f'{ten_sinh_vien}_{ma_sinh_vien}'
        student_folder_path = os.path.join(local_face_directory, student_folder_name)

        # Nếu folder đã tồn tại, xóa thư mục cũ
        if os.path.exists(student_folder_path):
            for root, dirs, files in os.walk(student_folder_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(student_folder_path)

        # Giải nén tệp zip đã giải mã vào thư mục face
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(student_folder_path)

        # Xóa file zip tạm
        os.remove(zip_filename)

        print(f"Đã cập nhật thư mục cho sinh viên: {student_folder_name}")
