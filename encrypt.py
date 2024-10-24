
import os
import zipfile
from cryptography.fernet import Fernet

# Tạo khóa mã hóa
key = Fernet.generate_key()
cipher_suite = Fernet(key)


# Hàm nén thư mục
def zip_folder(folder_path, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for foldername, subfolders, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zip_file.write(file_path, os.path.relpath(file_path, folder_path))


# Nén và mã hóa từng thư mục cá nhân trong "face"
def encrypt_and_zip_folder(folder_path):
    folder_name = os.path.basename(folder_path)

    # Tách lấy ID từ tên thư mục (giả sử tên là "name_ID")
    person_id = folder_name.split('_')[-1]

    # Nén thư mục
    zipped_folder = f'{folder_name}.zip'
    zip_folder(folder_path, zipped_folder)

    # Mã hóa tệp zip
    with open(zipped_folder, 'rb') as file:
        encrypted_data = cipher_suite.encrypt(file.read())

    # Trả về ID và dữ liệu mã hóa
    return person_id, encrypted_data


# Đường dẫn đến thư mục "face"
face_directory = 'face'

# Duyệt qua tất cả các thư mục con trong "face"
folders = [os.path.join(face_directory, folder) for folder in os.listdir(face_directory) if
           os.path.isdir(os.path.join(face_directory, folder))]

# Danh sách chứa các cặp ID và dữ liệu mã hóa
encrypted_folders = [encrypt_and_zip_folder(folder) for folder in folders]

# Lưu khóa mã hóa để sử dụng sau
with open('encryption_key.key', 'wb') as key_file:
    key_file.write(key)
