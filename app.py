import json
import shutil
import cv2
import os
from flask import Flask, request, render_template, redirect, url_for, session, flash
from datetime import date
from datetime import datetime
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import pandas as pd
import joblib
import pyodbc as p
from deepface import DeepFace

import function

app = Flask(__name__)
app.secret_key = os.urandom(24)

conn_str = ('DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER= Hacker303;'
            'DATABASE=QuanLyDiemDanh;'
            'Trusted_Connection=yes;')

imgBackground = cv2.imread("background.png")
nimgs = 5
datetoday = date.today().strftime("%m_%d_%y")
datetoday2 = date.today().strftime("%d-%B-%Y")
face_directory = 'face'
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
if not os.path.isdir('Attendance'):
    os.makedirs('Attendance')
if not os.path.isdir('face'):
    os.makedirs('face')
if not os.path.isdir('static/faces'):
    os.makedirs('static/faces')
if f'Attendance-{function.datetoday}.csv' not in os.listdir('Attendance'):
    with open(f'Attendance/Attendance-{function.datetoday}.csv', 'w') as f:
        f.write('ID,DateTime,MaMH,MaPH')


@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    # if not session['logged_in']:
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = function.get_user_from_db(username, password)

        if user:
            session['logged_in'] = True
            UId = user.UserID
            name = function.get_student_or_teacher(UId)
            session['name'] = name

            if 'AD' in UId:
                session['role'] = 'admin'
                return redirect('/admin')
            elif session['role'] == 'student':
                return redirect('/student')
            elif session['role'] == 'teacher':
                return redirect('/teacher')

        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html', error=error)


@app.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'POST':
        # Xử lý khi người dùng gửi form chọn môn học
        selected_subject = request.form.get('monhoc')
        print(selected_subject)

        # Kiểm tra nếu không có môn học nào được chọn
        if not selected_subject:
            subjects = function.load_subjects()
            return render_template('attendance.html', subjects=subjects,
                                   mess='Please select a subject.')

        # Bắt đầu quá trình điểm danh với môn học đã chọn
        subjects = function.load_subjects()
        if not any(os.path.isdir(os.path.join('face', folder)) for folder in os.listdir('face')):
            return render_template('attendance.html', totalreg=function.totalreg(), datetoday2=function.datetoday2,
                                   subjects=subjects,
                                   mess='There is no trained model in the static folder. Please add a new face to continue.')

        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Không thể mở camera")
                break

            # Trích xuất khuôn mặt từ khung hình
            faces = DeepFace.extract_faces(frame, detector_backend='opencv', enforce_detection=False)

            if len(faces) > 0:
                # Lấy thông tin khuôn mặt đầu tiên
                face_info = faces[0]
                face = face_info['face']
                facial_area = face_info['facial_area']
                x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

                # Vẽ hình chữ nhật quanh khuôn mặt
                cv2.rectangle(frame, (x, y), (x + w, y + h), (86, 32, 251), 1)
                cv2.rectangle(frame, (x, y), (x + w, y - 40), (86, 32, 251), -1)

                db_path = "face"
                matched = False
                for root, dirs, files in os.walk(db_path):
                    # Duyệt qua từng file ảnh trong các thư mục con
                    for file in files:
                        img_path = os.path.join(root, file)

                        # Tìm kiếm khuôn mặt khớp nhất trong thư mục database
                        matched_faces = DeepFace.find(img_path=face, db_path=root, enforce_detection=False)

                        if len(matched_faces) > 0:
                            df = matched_faces[0]
                            if not df.empty:
                                matched_file = df.iloc[0].identity

                                matched_folder = os.path.basename(os.path.dirname(matched_file))
                                identified_person = os.path.splitext(matched_folder)[0]

                                # Hiển thị tên người được nhận diện
                                cv2.putText(frame, identified_person, (x, y - 15), cv2.FONT_HERSHEY_COMPLEX, 1,
                                            (255, 255, 255), 1)
                                matched = True
                                break
                    if matched:
                        break
                    if not matched:
                        cv2.putText(frame, "Unknown", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            # Resize khung hình nếu cần
            resized_frame = cv2.resize(frame, (640, 480))
            imgBackground[162:162 + 480, 55:55 + 640] = resized_frame
            cv2.imshow('Attendance', imgBackground)
            cv2.setWindowProperty('Attendance', cv2.WND_PROP_TOPMOST, 1)

            # Nhấn 'q' để thoát
            if cv2.waitKey(1) == ord('q'):
                break

        # Ghi lại thông tin điểm danh
        function.add_attendance(identified_person, selected_subject)
        cap.release()
        cv2.destroyAllWindows()
        subjects = function.load_subjects()
        return render_template('attendance.html', totalreg=function.totalreg(), datetoday2=function.datetoday2,
                               subjects=subjects)
    elif request.method == 'GET':
        # Xử lý khi hiển thị giao diện lần đầu
        subjects = function.load_subjects()
        return render_template('attendance.html', totalreg=function.totalreg(), datetoday2=function.datetoday2,
                               subjects=subjects)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    session['name'] = "Admin"
    welcome_message = f"Xin chào {session['name']}!"
    return render_template('Menu_admin.html', totalreg=function.totalreg(), welcome_message=welcome_message)


@app.route('/student', methods=['GET', 'POST'])
def student():
    welcome_message = f"Xin chào Sinh viên {session['name']}!"
    subjects = function.load_subjects()
    return render_template('attendance.html',
                           totalreg=function.totalreg(),
                           datetoday2=function.datetoday2, subjects=subjects,
                           welcome_message=welcome_message)


@app.route('/teacher', methods=['GET', 'POST'])
def teacher():
    return redirect('/find')


@app.route('/find', methods=['GET', 'POST'])
def find():
    role = session['role']
    if role == 'admin':
        welcome_message = f"Xin chào {session['name']}!"
    else:
        welcome_message = f"Xin chào Giáo viên {session['name']}!"
    return render_template('find.html', welcome_message=welcome_message)


@app.route('/modify', methods=['GET', 'POST'])
def modify():
    return render_template('modifyUser_Main.html', totalreg=function.totalreg())


@app.route('/modify/add', methods=['POST', 'GET'])
def add():
    if request.method == 'POST':
        role = request.form.get('role')
        if role == 'teacher':
            return redirect(url_for('addTutor'))
        elif role == 'student':
            print("student")
            return redirect(url_for('addStudent'))

    return render_template('modifyUser_Add.html')


@app.route('/modify/add/student', methods=['GET', 'POST'])
def addStudent():
    if request.method == 'POST':
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        newuserid = request.form.get('newuserid')
        newusername = request.form.get('newusername')
        password = request.form.get('password')
        name = request.form.get('name')
        namsinh = request.form['namsinh']
        quequan = request.form['quequan']
        malop = request.form['malop']
        # Kiểm tra xem người dùng đã tồn tại chưa
        Cursor_call.execute('SELECT COUNT(*) FROM NguoiDung WHERE UserID = ?', (newuserid,))
        exists = Cursor_call.fetchone()[0]

        if exists > 0:
            return "Người dùng đã tồn tại"

        # Thêm người dùng vào cơ sở dữ liệu
        Cursor_call.execute('INSERT INTO NguoiDung (UserID, Username, Password, Status) VALUES (?, ?, ?, ?)',
                            (newuserid, newusername, password, "active"))

        Cursor_call.execute(
            'INSERT INTO SinhVien (MaSinhVien, TenSinhVien, NamSinh, QueQuan, MaLop) VALUES (?, ?, ?, ?, ?)',
            (newuserid, name, namsinh, quequan, malop))
        function.addStudentRaw(newusername, newuserid)
        Connection.commit()
        return redirect(url_for('admin'))
    return render_template('modifyUser_Add_Student.html')


@app.route('/modify/add/tutor', methods=['GET', 'POST'])
def addTutor():
    if request.method == 'POST':
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        newuserid = request.form.get('newuserid')
        newusername = request.form.get('newusername')
        password = request.form.get('password')
        name = request.form.get('name')
        khoa = request.form['khoa']

        # Kiểm tra xem người dùng đã tồn tại chưa
        Cursor_call.execute('SELECT COUNT(*) FROM NguoiDung WHERE UserID = ?', (newuserid,))
        exists = Cursor_call.fetchone()[0]

        if exists > 0:
            return "Người dùng đã tồn tại"

        # Thêm người dùng vào cơ sở dữ liệu
        Cursor_call.execute('INSERT INTO NguoiDung (UserID, Username, Password, Status) VALUES (?, ?, ?, ?)',
                            (newuserid, newusername, password, "active"))

        Cursor_call.execute(
            'INSERT INTO GiaoVien (MaGiaoVien, TenGiaoVien, Khoa) VALUES (?, ?, ?)',
            (newuserid, name, khoa))
        Connection.commit()
        return redirect('/admin')
    return render_template('modifyUser_Add_Tutor.html')


@app.route('/modify/change', methods=['GET', 'POST'])
def change():
    if request.method == 'POST':
        name = request.form['name'].strip()
        userid = request.form['userid'].strip()
        session['userid'] = userid
        # student, teacher = get_user_info(userid)
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        if userid:
            get_user_info(userid)
            return redirect(url_for('changing'))
        elif name:
            query = "SELECT MaSinhVien FROM SinhVien WHERE TenSinhVien LIKE ?"
            params = (f"%{name}%",)
            Cursor_call.execute(query, params)
            userid = Cursor_call.fetchall()
            student, teacher = get_user_info(userid)
            if student:
                session['role'] = 'student'
                return redirect(url_for('changing'))
            elif teacher:
                session['role'] = 'teacher'
                return redirect(url_for('changing'))


        else:
            return render_template('modifyUser_Change.html')

    return render_template('modifyUser_Change.html')


@app.route('/modify/changing', methods=['GET', 'POST'])
def changing():
    if request.method == 'POST':
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        role = session['role']
        userid = session['userid']
        query = 'select UserID,Username,Password From NguoiDung Where UserID = ?'

        if role == 'student':
            new_ma_sv = request.form['newuserid']
            new_ten_sv = request.form['name']
            new_namsinh = request.form['namsinh']
            new_quequan = request.form['quequan']
            new_malop = request.form['malop']
            new_username = request.form['newusername']
            new_password = request.form['password']

            # Cập nhật bảng SinhVien
            Cursor_call.execute('''
                                        UPDATE SinhVien 
                                        SET MaSinhVien = ?, TenSinhVien = ?, NamSinh = ?, QueQuan = ?, MaLop = ?
                                        WHERE MaGiaoVien = ?
                                    ''', (new_ma_sv, new_ten_sv, new_namsinh, new_quequan, new_malop, userid))

            # Cập nhật bảng NguoiDung
            Cursor_call.execute('''
                                        UPDATE NguoiDung 
                                        SET Username = ?, Password = ?
                                        WHERE UserID = ?
                                    ''', (new_username, new_password, userid))

            # Lưu thay đổi vào cơ sở dữ liệu
            Connection.commit()
            flash("success")
            return redirect(url_for('admin'))
        elif role == 'teacher':
            new_ma_gv = request.form['newuserid']
            new_ten_gv = request.form['name']
            new_khoa = request.form['khoa']
            new_username = request.form['newusername']
            new_password = request.form['password']

            # Cập nhật bảng GiaoVien
            Cursor_call.execute('''
                            UPDATE GiaoVien 
                            SET MaGiaoVien = ?, TenGiaoVien = ?, Khoa = ?
                            WHERE MaGiaoVien = ?
                        ''', (new_ma_gv, new_ten_gv, new_khoa, userid))

            # Cập nhật bảng NguoiDung
            Cursor_call.execute('''
                            UPDATE NguoiDung 
                            SET Username = ?, Password = ?
                            WHERE UserID = ?
                        ''', (new_username, new_password, userid))

            # Lưu thay đổi vào cơ sở dữ liệu
            Connection.commit()
            flash("success")
            return redirect(url_for('admin'))
        return redirect(url_for('change'))
    if request.method == 'GET':
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        role = session['role']
        userid = session['userid']
        if role == 'teacher':
            teacher = get_user_info(userid)[1]  # Lấy dữ liệu giáo viên
            if teacher:  # Kiểm tra nếu có dữ liệu giáo viên
                MaGiaoVien = teacher[0][0]  # Mã Giáo Viên
                TenGiaoVien = teacher[0][1]  # Tên Giáo Viên
                Khoa = teacher[0][2]  # Khoa

                # Lấy thông tin từ bảng NguoiDung
                Cursor_call.execute('SELECT UserID, Username, Password FROM NguoiDung WHERE UserID = ?', (userid,))
                user = Cursor_call.fetchone()
                if user:  # Kiểm tra nếu có thông tin người dùng
                    UserID = user[0]
                    Username = user[1]
                    Password = user[2]  # Chú ý chỉ số này là 2 chứ không phải 3
                    return render_template('confirm_Change_GiaoVien.html',
                                           MaGiaoVien=MaGiaoVien,
                                           TenGiaoVien=TenGiaoVien,
                                           Khoa=Khoa,
                                           UserID=UserID,
                                           Username=Username,
                                           Password=Password)
                else:
                    flash("Không tìm thấy thông tin người dùng.")
                    return redirect(url_for('change'))
            else:
                flash("Không tìm thấy giáo viên với mã đã nhập.")
                return redirect(url_for('change'))
        elif role == 'student':
            student = get_user_info(userid)
            print(student)
            Cursor_call.execute('SELECT UserID, Username,Password FROM NguoiDung WHERE UserID = ?', (userid,))
            user = Cursor_call.fetchall()
            MaSinhVien = student[0][0]
            TenSinhVien = student[0][1]
            NamSinh = student[0][2]
            QueQuan = student[0][3]
            MaLop = student[0][4]
            Username = user[0][1]
            Password = user[0][2]
            return render_template('confirm_Change_SinhVien.html',
                                   MaSinhVien=MaSinhVien,
                                   TenSinhVien=TenSinhVien,
                                   NamSinh=NamSinh,
                                   QueQuan=QueQuan,
                                   MaLop=MaLop,
                                   Username=Username,
                                   Password=Password)

        return redirect(url_for('change'))


@app.route('/modify/remove', methods=['GET', 'POST'])
def remove():
    if request.method == 'POST':
        userid = request.form.get('userid')

        cursor.execute("SELECT * FROM SinhVien WHERE MaSinhVien = ?", (userid,))
        student = cursor.fetchone()
        role = 'student'
        print(role+'remove')
        if not student:
            cursor.execute("SELECT * FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))
            teacher = cursor.fetchone()
            print (teacher)
            role = 'teacher'
            print(role+'remove')
            if not teacher:
                er = 'not found'
                print(role+'remove')
                return render_template('modifyUser_Remove.html', er=er)

        if role == 'student':
            return render_template('confirm_SinhVien.html', MaSinhVien=student[0], TenSinhVien=student[1],
                                   NamSinh=student[2], QueQuan=student[3], MaLop=student[4])
        elif role == 'teacher':
            return render_template('confirm_GiaoVien.html', MaGiaoVien=teacher[0], TenGiaoVien=teacher[1],
                                   Khoa=teacher[2])
        # Handle confirmation
        if request.form.get('confirm') == 'Yes':
            print("yes")
            username = delete_user(userid, role)
            if username:
                # function.remove_user_image_folder(username, userid)
                print(f"{role.capitalize()} user {userid} successfully removed.", "success")
                return redirect(url_for('admin'))
            else:
                er = "Failed to delete user."
                return render_template('modifyUser_Remove.html', er=er)

        # Render confirmation template based on role


    return render_template('modifyUser_Remove.html')


def delete_user(userid, role):
    if role == 'student':
        print(role+'delete')
        cursor.execute("select Username from NguoiDung where UserID = ?", (userid,))
        username = cursor.fetchone()
        print(username)

        cursor.execute("DELETE from DiemDanh where MaSinhVien = ?", (userid,))
        cursor.execute("DELETE FROM SinhVien WHERE MaSinhVien = ?", (userid,))

    elif role == 'teacher':
        print(role+'delete')
        cursor.execute("select Username from NguoiDung where UserID = ?", (userid,))
        username = cursor.fetchone()
        print(username)
        cursor.execute("DELETE FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))
        Connection.commit()
    return username[0] if username else None


def get_user_info(userid):
    cursor.execute("SELECT * FROM SinhVien WHERE MaSinhVien = ?", (userid,))
    student = cursor.fetchone()
    session['role'] = 'student'
    if not student:
        cursor.execute("SELECT * FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))
        teacher = cursor.fetchone()
        session['role'] = 'teacher'
        return teacher
    return student


@app.route('/modify/confirm', methods=['GET', 'POST'])
def confirm():
    # role = session['role']
    userid = session['userid']
    Connection = p.connect(conn_str)
    cursor = Connection.cursor()

    cursor.execute("SELECT * FROM SinhVien WHERE MaSinhVien = ?", (userid,))
    # row = cursor.fetchone()
    # student =row
    student = cursor.fetchone()
    print(student)
    role = 'student'
    if not student:
        cursor.execute("SELECT * FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))
        teacher = cursor.fetchone()
        role = 'teacher'

    if role == 'student':
        if request.form.get('confirm') == 'Yes':
            username = function.delete_user(userid, role)
            print(username + " " + userid)
            function.remove_user_image_folder(username, userid)
            function.train_model()
            return redirect(url_for('admin'))
        return render_template('confirm_SinhVien.html', MaSinhVien=student[0], TenSinhVien=student[1],
                               NamSinh=student[2], QueQuan=student[3], MaLop=student[4])
    elif role == 'teacher':
        if request.form.get('confirm') == 'Yes':
            username = function.delete_user(userid, role)
            # print(username + " " + userid)
            function.remove_user_image_folder(username, userid)
            # Clean up session
            function.train_model()
            return redirect(url_for('admin'))
        return render_template('confirm_GiaoVien.html', MaGiaoVien=teacher[0], TenGiaoVien=teacher[1], Khoa=teacher[2])
    return redirect(url_for('remove'))


@app.route('/find/attendance', methods=['GET', 'POST'])
def find_Attendance():
    if request.method == 'POST':
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = """
            SELECT MaSinhVien, ThoiGianDiemDanh, MaMonHoc, MaPhong
            FROM DiemDanh
            WHERE ThoiGianDiemDanh BETWEEN ? AND ?
        """
        query_same = """
            SELECT MaSinhVien, ThoiGianDiemDanh, MaMonHoc, MaPhong
            FROM DiemDanh
            WHERE CAST(ThoiGianDiemDanh AS DATE) = ?
            """

        start_date = request.form['start']
        end_date = request.form['end']

        if not start_date or not end_date:
            error = "Please choose both start and end dates."
            return render_template('find_Attendance.html', error=error)
        elif start_date == end_date:
            Cursor_call.execute(query_same, (start_date,))
            attendance = Cursor_call.fetchall()
            Connection.close()
        else:
            Cursor_call.execute(query, (start_date, end_date))
            attendance = Cursor_call.fetchall()
            Connection.close()

        return render_template('attendanceTable.html', attendance=attendance)

    # Nếu là yêu cầu GET, chỉ hiển thị form
    return render_template('find_Attendance.html')


@app.route('/find/student', methods=['GET', 'POST'])
def find_Student():
    if request.method == 'POST':
        name = request.form['name'].strip()  # Loại bỏ khoảng trắng thừa
        id = request.form['id'].strip()
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = ""
        params = []
        # Kiểm tra xem trường name hoặc id có bị trống không
        if id and name:
            query = "SELECT * FROM SinhVien WHERE MaSinhVien = ? AND TenSinhVien LIKE ?"
            params = (id, f"%{name}%")
            # Nếu chỉ có ID
        elif id:
            query = "SELECT * FROM SinhVien WHERE MaSinhVien = ?"
            params = (id,)
            # Nếu chỉ có Name, sử dụng điều kiện LIKE
        elif name:
            query = "SELECT * FROM SinhVien WHERE TenSinhVien LIKE ?"
            params = (f"%{name}%",)
        Cursor_call.execute(query, params)
        students = Cursor_call.fetchall()
        if not students:
            error_message = "No students found with the given information."
            return render_template('find_Student.html', error_message=error_message)

        # Nếu tìm thấy, hiển thị kết quả
        return render_template('studentTable.html', students=students)
    return render_template('find_Student.html')


@app.route('/find/teacher', methods=['GET', 'POST'])
def find_Teacher():
    if request.method == 'POST':
        name = request.form['name'].strip()  # Loại bỏ khoảng trắng thừa
        id = request.form['id'].strip()
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = ""
        params = []
        # Kiểm tra xem trường name hoặc id có bị trống không
        if id and name:
            query = "SELECT * FROM GiaoVien WHERE MaGiaoVien = ? AND TenGiaoVien LIKE ?"
            params = (id, f"%{name}%")
            # Nếu chỉ có ID
        elif id:
            query = "SELECT * FROM GiaoVien WHERE MaGiaoVien = ?"
            params = (id,)
            # Nếu chỉ có Name, sử dụng điều kiện LIKE
        elif name:
            query = "SELECT * FROM GiaoVien WHERE TenGiaoVien LIKE ?"
            params = (f"%{name}%",)
        Cursor_call.execute(query, params)
        teacher = Cursor_call.fetchall()
        if not teacher:
            error_message = "No teacher found with the given information."
            return render_template('find_Teacher.html', error_message=error_message)

            # Nếu tìm thấy, hiển thị kết quả
        return render_template('teacherTable.html', teacher=teacher)
    return render_template('find_Teacher.html')


@app.route('/find/class', methods=['GET', 'POST'])
def find_class():
    if request.method == 'POST':
        name = request.form['name'].strip()  # Loại bỏ khoảng trắng thừa
        id = request.form['id'].strip()
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = ""
        params = []
        # Kiểm tra xem trường name hoặc id có bị trống không
        if id and name:
            query = "SELECT * FROM Lop WHERE MaLop = ? AND TenLop LIKE ?"
            params = (id, f"%{name}%")
            # Nếu chỉ có ID
        elif id:
            query = "SELECT * FROM Lop WHERE MaLop = ?"
            params = (id,)
            # Nếu chỉ có Name, sử dụng điều kiện LIKE
        elif name:
            query = "SELECT * FROM Lop WHERE TenLop LIKE ?"
            params = (f"%{name}%",)
        Cursor_call.execute(query, params)
        Class = Cursor_call.fetchall()
        if not Class:
            error_message = "No class found with the given information."
            return render_template('find_Class.html', error_message=error_message)

        # Nếu tìm thấy, hiển thị kết quả
        return render_template('classTable.html', Class=Class)
    return render_template('find_Class.html')


@app.route('/find/sub', methods=['GET', 'POST'])  # Cần Thêm Tìm Theo Mã Giáo Viên
def find_subject():
    if request.method == 'POST':
        name = request.form['name'].strip()  # Loại bỏ khoảng trắng thừa
        id = request.form['id'].strip()
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = ""
        params = []
        # Kiểm tra xem trường name hoặc id có bị trống không
        if id and name:
            query = "SELECT * FROM MonHoc WHERE MaMonHoc = ? AND TenMonHoc LIKE ?"
            params = (id, f"%{name}%")
            # Nếu chỉ có ID
        elif id:
            query = "SELECT * FROM MonHoc WHERE MaMonHoc = ?"
            params = (id,)
            # Nếu chỉ có Name, sử dụng điều kiện LIKE
        elif name:
            query = "SELECT * FROM MonHoc WHERE TenMonHoc LIKE ?"
            params = (f"%{name}%",)
        Cursor_call.execute(query, params)
        sub = Cursor_call.fetchall()
        if not sub:
            error_message = "No Subject found with the given information."
            return render_template('find_Subject.html', error_message=error_message)

        # Nếu tìm thấy, hiển thị kết quả
        return render_template('subTable.html', sub=sub)
    return render_template('find_Subject.html')


@app.route('/find/room', methods=['GET', 'POST'])
def find_room():
    if request.method == 'POST':
        name = request.form['name'].strip()  # Loại bỏ khoảng trắng thừa
        id = request.form['id'].strip()
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        query = ""
        params = []
        # Kiểm tra xem trường name hoặc id có bị trống không
        if id and name:
            query = "SELECT * FROM Phong WHERE MaPhong = ? AND TenPhong LIKE ?"
            params = (id, f"%{name}%")
            # Nếu chỉ có ID
        elif id:
            query = "SELECT * FROM Phong WHERE MaPhong = ?"
            params = (id,)
            # Nếu chỉ có Name, sử dụng điều kiện LIKE
        elif name:
            query = "SELECT * FROM Phong WHERE TenPhong LIKE ?"
            params = (f"%{name}%",)
        Cursor_call.execute(query, params)
        room = Cursor_call.fetchall()
        if not room:
            error_message = "No room found with the given information."
            return render_template('find_Room.html', error_message=error_message)

        # Nếu tìm thấy, hiển thị kết quả
        return render_template('roomTable.html', room=room)
    return render_template('find_Room.html')


@app.route('/logout')
def logout():
    session.pop('username', None)  # Xóa session đăng nhập
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
