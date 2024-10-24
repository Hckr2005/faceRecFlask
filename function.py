import os
import zipfile
from cryptography.fernet import Fernet

import json
import shutil
import cv2
from flask import Flask, request, render_template, redirect, url_for, session, flash
from datetime import date
from datetime import datetime
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import pandas as pd
import joblib
import pyodbc as p
from deepface import DeepFace

nimgs = 5
datetoday = date.today().strftime("%m_%d_%y")
datetoday2 = date.today().strftime("%d-%B-%Y")
face_directory = 'face'
conn_str = ('DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER= Hacker303;'
            'DATABASE=QuanLyDiemDanh;'
            'Trusted_Connection=yes;')
Connection = p.connect(conn_str)
cursor = Connection.cursor()
update_query = '''
    UPDATE SinhVien
    SET FolderAnh = ?
    WHERE MaSinhVien = ?
'''
select_query = '''
        SELECT MaSinhVien, TenSinhVien, FolderAnh 
        FROM SinhVien
    '''


def EncryptAndZip():
    key = Fernet.generate_key()
    cipher_suite = Fernet(key)

    # Hàm nén thư mục
    def zip_folder(folder_path, output_path):
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for foldername, subfolders, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))

    # Nén và mã hóa từng thư mục cá nhân
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

        # Xóa file zip tạm sau khi mã hóa
        os.remove(zipped_folder)

        # Trả về ID và dữ liệu mã hóa
        return person_id, encrypted_data

    # Duyệt qua tất cả các thư mục con trong "face"
    folders = [os.path.join(face_directory, folder) for folder in os.listdir(face_directory)
               if os.path.isdir(os.path.join(face_directory, folder))]

    # Danh sách chứa các cặp ID và dữ liệu mã hóa
    encrypted_folders = [encrypt_and_zip_folder(folder) for folder in folders]

    return encrypted_folders


def SQLpush(encrypted_folders):
    # Đẩy từng thư mục lên SQL Server
    for person_id, encrypted_data in encrypted_folders:
        cursor.execute(update_query, (encrypted_data, person_id))

    # Xác nhận các thay đổi
    conn_str.commit()

    # Đóng kết nối
    cursor.close()
    conn_str.close()


def SQLpull(encryption_key_path):
    # Đọc khóa mã hóa từ tệp để giải mã
    with open(encryption_key_path, 'rb') as key_file:
        key = key_file.read()

    cipher_suite = Fernet(key)

    cursor.execute(select_query)

    # Lưu tất cả dữ liệu mã hóa vào danh sách
    encrypted_folders = cursor.fetchall()

    cursor.close()
    conn_str.close()

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
            student_folder_path = os.path.join(face_directory, student_folder_name)

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


def get_attendance_data():
    Connection = p.connect(conn_str)
    Cursor_call = Connection.cursor()
    today = datetime.now().date().strftime('%Y-%m-%d')
    query = """
        SELECT MaSinhVien, ThoiGianDiemDanh, MaMonHoc, MaPhong 
        FROM DiemDanh 
        WHERE CONVERT(DATE, ThoiGianDiemDanh) = ?
        """
    Cursor_call.execute(query, (today,))
    rows = Cursor_call.fetchall()
    Connection.close()
    return rows


def totalreg():
    return len(os.listdir('face'))


def identify_face(facearray):
    model = joblib.load('static/face_recognition_model.pkl')
    return model.predict(facearray)


def train_model():
    faces = []
    labels = []
    userlist = os.listdir('static/faces')
    for user in userlist:
        for imgname in os.listdir(f'static/faces/{user}'):
            img_path = f'static/faces/{user}/{imgname}'
            img = cv2.imread(img_path)

            # Kiểm tra nếu ảnh được đọc thành công
            if img is None:
                print(f"Lỗi: Không thể đọc ảnh {img_path}")
                continue

            resized_face = cv2.resize(img, (50, 50))
            faces.append(resized_face.ravel())
            labels.append(user)

    if len(faces) > 0:  # Kiểm tra nếu có dữ liệu để train
        faces = np.array(faces)
        knn = KNeighborsClassifier(n_neighbors=5)
        knn.fit(faces, labels)
        joblib.dump(knn, 'static/face_recognition_model.pkl')
        print("Model đã được huấn luyện thành công và lưu.")
    else:
        print("Không có dữ liệu để train model.")


# def extract_attendance():
#     df = pd.read_csv(f'Attendance/Attendance-{datetoday}.csv')
#     ID = df['ID']
#     DateTime = df['DateTime']
#     MaMH = df['MaMH']
#     MaPH = df['MaPH']
#     l = len(df)
#     return ID, DateTime, MaMH, MaPH, l


def getRoomId():
    default = "P01"
    # Cursor_call.execute('select MaPhong from Phong')
    # roomId = Cursor_call.fetchall()
    return default


def add_attendance(name, selected_subject):
    start_time_1 = datetime.strptime("7:00", "%H:%M").time()
    end_time_1 = datetime.strptime("12:30", "%H:%M").time()
    start_time_2 = datetime.strptime("13:00", "%H:%M").time()
    end_time_2 = datetime.strptime("18:30", "%H:%M").time()

    compare_current_time = datetime.now().time().replace(microsecond=0)
    current_time = datetime.now().replace(microsecond=0)
    SId = selected_subject
    RId = getRoomId()
    userid = name.split('_')[1]

    Connection = p.connect(conn_str)
    Cursor_call = Connection.cursor()

    # Kiểm tra khoảng thời gian sáng hay chiều
    if compare_current_time <= end_time_1:
        current_sec = "sang"
    else:
        current_sec = "chieu"

    # Kiểm tra trong CSDL xem người dùng đã điểm danh trong khoảng thời gian này chưa
    if current_sec == "sang":
        Cursor_call.execute('''SELECT COUNT(*)
                               FROM DiemDanh 
                               WHERE MaSinhVien = ? AND MaMonHoc = ? 
                               AND ThoiGianDiemDanh >= ? AND ThoiGianDiemDanh <= ?''',
                            (userid, SId, current_time.replace(hour=7, minute=0, second=0),
                             current_time.replace(hour=12, minute=30, second=0)))
    else:
        Cursor_call.execute('''SELECT COUNT(*)
                               FROM DiemDanh 
                               WHERE MaSinhVien = ? AND MaMonHoc = ? 
                               AND ThoiGianDiemDanh >= ? AND ThoiGianDiemDanh <= ?''',
                            (userid, SId, current_time.replace(hour=13, minute=0, second=0),
                             current_time.replace(hour=18, minute=30, second=0)))

    already_checked_in = Cursor_call.fetchone()[0] > 0

    # Nếu chưa điểm danh, thêm bản ghi mới
    if not already_checked_in:
        # Ghi vào CSV
        with open(f'Attendance/Attendance-{datetoday}.csv', 'a') as f:
            f.write(f'\n{userid},{current_time},{SId},{RId}')

        # Ghi vào CSDL
        Cursor_call.execute(
            'INSERT INTO DiemDanh (MaSinhVien, ThoiGianDiemDanh, MaMonHoc, MaPhong) VALUES (?, ?, ?, ?)',
            (userid, current_time.strftime("%Y-%m-%d %H:%M:%S"), SId, RId))
        Connection.commit()

    Connection.close()


def getallusers():
    userlist = os.listdir('face')
    names = []
    rolls = []
    l = len(userlist)

    for i in userlist:
        name, roll = i.split('_')
        names.append(name)
        rolls.append(roll)

    return userlist, names, rolls, l


def load_subjects():
    Connection = p.connect(conn_str)
    Cursor_Call = Connection.cursor()
    subjects = {}

    Cursor_Call.execute("SELECT MaMonHoc, TenMonHoc FROM MonHoc")
    rows = Cursor_Call.fetchall()

    for row in rows:
        subject_code = row[0]  # MaMonHoc
        subject_name = row[1]  # TenMonHoc
        subjects[subject_name] = subject_code  # Lưu vào dictionary

    return subjects


def get_user_from_db(username, password):
    # conn_str = p.connect('DRIVER={ODBC Driver 17 for SQL Server};'
    #                      'SERVER= Hacker303;'
    #                      'DATABASE=QuanLyDiemDanh;'
    #                      'Trusted_Connection=yes;')
    # Connection = p.connect(conn_str)
    # Cursor_Call = Connection.cursor()
    query = """
            SELECT UserID, Username, Password 
            FROM NguoiDung 
            WHERE Username = ? AND Password = ?
            """
    cursor.execute(query, (username, password))
    return cursor.fetchone()


def get_student_or_teacher(UId):
    Connection = p.connect(conn_str)
    Cursor_Call = Connection.cursor()

    # Kiểm tra trong bảng SinhVien
    query_student = "SELECT TenSinhVien FROM SinhVien WHERE MaSinhVien = ?"
    Cursor_Call.execute(query_student, (UId,))
    student = Cursor_Call.fetchone()

    if student:
        session['role'] = 'student'
        # Nếu tìm thấy trong bảng SinhVien
        return student[0]

    # Kiểm tra trong bảng GiaoVien nếu không tìm thấy trong bảng SinhVien
    query_teacher = "SELECT TenGiaoVien FROM GiaoVien WHERE MaGiaoVien = ?"
    Cursor_Call.execute(query_teacher, (UId,))
    teacher = Cursor_Call.fetchone()

    if teacher:
        session['role'] = 'teacher'
        # Nếu tìm thấy trong bảng GiaoVien
        return teacher[0]

    return None


def addStudentRaw(newusername, newuserid):
    userimagefolder = 'face/' + newusername + '_' + newuserid
    if not os.path.isdir(userimagefolder):
        os.makedirs(userimagefolder)
    i, j = 0, 0
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Không thể mở camera")
            break
        faces = DeepFace.extract_faces(frame, detector_backend="opencv", align=True)
        for face_info in faces:
            facial_area = face_info['facial_area']
            x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

            # Vẽ hình chữ nhật quanh khuôn mặt
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 20), 2)
            cv2.putText(frame, f'Images Captured: {i}/{nimgs}', (30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 20), 2, cv2.LINE_AA)

            # Lưu khuôn mặt sau mỗi 5 khung hình
            if j % 5 == 0:
                face = frame[y:y + h, x:x + w]
                name = newuserid + '_' + str(i) + '.jpg'
                cv2.imwrite(os.path.join(userimagefolder, name), face)
                i += 1  # Tăng số lượng ảnh đã lưu

            j += 1  # Tăng biến đếm số khung hình đã xử lý

            # Dừng khi đã chụp đủ số ảnh cần thiết
        if j == nimgs * 5:
            break

            # Hiển thị khung hình đang chụp
        cv2.imshow('Adding new User', frame)

        # Nhấn 'Esc' để thoát
        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


def find_byID(userid):
    Connection = p.connect(conn_str)
    Cursor_call = Connection.cursor()
    query = """
            SELECT * 
            FROM SinhVien 
            WHERE MaSinhVien LIKE ?
            """
    search_pattern = f"%{userid}%"
    Cursor_call.execute(query, (userid,))
    rows = Cursor_call.fetchall()
    Connection.close()
    return rows


def find_byName(username):
    Connection = p.connect(conn_str)
    Cursor_call = Connection.cursor()
    query = """
            SELECT * 
            FROM SinhVien 
            WHERE TenSinhVien LIKE ?
            """
    search_pattern = f"%{username}%"  # Thêm ký tự '%' trước và sau để tìm kiếm chứa ký tự
    Cursor_call.execute(query, (search_pattern,))
    rows = Cursor_call.fetchall()
    Connection.close()
    return rows





def remove_user_image_folder(username, userid):
    user_image_folder = os.path.join('static/faces', f"{username}_{userid}")
    if os.path.exists(user_image_folder):
        shutil.rmtree(user_image_folder)
        print(f"Deleted folder: {user_image_folder}")
    else:
        print(f"Folder {user_image_folder} not found.")
