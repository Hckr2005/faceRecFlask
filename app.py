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

app = Flask(__name__)
app.secret_key = os.urandom(24)

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER= Hacker303;'
    'DATABASE=QuanLyDiemDanh;'
    'Trusted_Connection=yes;')
nimgs = 10
imgBackground = cv2.imread("background.png")
datetoday = date.today().strftime("%m_%d_%y")
datetoday2 = date.today().strftime("%d-%B-%Y")
face_detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
if not os.path.isdir('Attendance'):
    os.makedirs('Attendance')
if not os.path.isdir('static'):
    os.makedirs('static')
if not os.path.isdir('static/faces'):
    os.makedirs('static/faces')
if f'Attendance-{datetoday}.csv' not in os.listdir('Attendance'):
    with open(f'Attendance/Attendance-{datetoday}.csv', 'w') as f:
        f.write('ID,DateTime,MaMH,MaPH')


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
    return len(os.listdir('static/faces'))


def extract_faces(img):
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_points = face_detector.detectMultiScale(gray, 1.2, 5, minSize=(20, 20))
        return face_points
    except:
        return []


def identify_face(facearray):
    model = joblib.load('static/face_recognition_model.pkl')
    return model.predict(facearray)


def train_model():
    faces = []
    labels = []
    userlist = os.listdir('static/faces')
    for user in userlist:
        for imgname in os.listdir(f'static/faces/{user}'):
            img = cv2.imread(f'static/faces/{user}/{imgname}')
            resized_face = cv2.resize(img, (50, 50))
            faces.append(resized_face.ravel())
            labels.append(user)
    faces = np.array(faces)
    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(faces, labels)
    joblib.dump(knn, 'static/face_recognition_model.pkl')


def extract_attendance():
    df = pd.read_csv(f'Attendance/Attendance-{datetoday}.csv')
    ID = df['ID']
    DateTime = df['DateTime']
    MaMH = df['MaMH']
    MaPH = df['MaPH']
    l = len(df)
    return ID, DateTime, MaMH, MaPH, l


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
    userlist = os.listdir('static/faces')
    names = []
    rolls = []
    l = len(userlist)

    for i in userlist:
        name, roll = i.split('_')
        names.append(name)
        rolls.append(roll)

    return userlist, names, rolls, l


def load_subjects():
    subjects = {}
    with open('MonHoc.txt', 'r', encoding='utf-8') as f:
        for line in f:
            subject_name, subject_code = line.strip().split('|')
            subjects[subject_name] = subject_code
    return subjects


def get_user_from_db(username, password):
    Connection = p.connect(conn_str)
    Cursor_Call = Connection.cursor()
    query = """
            SELECT UserID, Username, Password 
            FROM NguoiDung 
            WHERE Username = ? AND Password = ?
            """
    Cursor_Call.execute(query, (username, password))
    return Cursor_Call.fetchone()


def get_student_or_teacher(UId):
    Connection = p.connect(conn_str)
    Cursor_Call = Connection.cursor()

    # Kiểm tra trong bảng SinhVien
    query_student = "SELECT TenSinhVien FROM SinhVien WHERE MaSinhVien = ?"
    Cursor_Call.execute(query_student, (UId,))
    student = Cursor_Call.fetchone()

    if student:
        # Nếu tìm thấy trong bảng SinhVien
        return student[0]

    # Kiểm tra trong bảng GiaoVien nếu không tìm thấy trong bảng SinhVien
    query_teacher = "SELECT TenGiaoVien FROM GiaoVien WHERE MaGiaoVien = ?"
    Cursor_Call.execute(query_teacher, (UId,))
    teacher = Cursor_Call.fetchone()

    if teacher:
        # Nếu tìm thấy trong bảng GiaoVien
        return teacher[0]

    return None


def addStudentRaw(newusername, newuserid):
    userimagefolder = 'static/faces/' + newusername + '_' + newuserid
    if not os.path.isdir(userimagefolder):
        os.makedirs(userimagefolder)
    i, j = 0, 0
    cap = cv2.VideoCapture(0)
    while 1:
        _, frame = cap.read()
        faces = extract_faces(frame)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 20), 2)
            cv2.putText(frame, f'Images Captured: {i}/{nimgs}', (30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 20), 2, cv2.LINE_AA)
            if j % 5 == 0:
                name = newusername + '_' + str(i) + '.jpg'
                cv2.imwrite(userimagefolder + '/' + name, frame[y:y + h, x:x + w])
                i += 1
            j += 1
        if j == nimgs * 5:
            break
        cv2.imshow('Adding new User', frame)
        if cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    print('Training Model')
    train_model()


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


def get_user_info(userid):
    with p.connect(conn_str) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM SinhVien WHERE MaSinhVien = ?", (userid,))
        student = cursor.fetchone()
        cursor.execute("SELECT * FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))
        teacher = cursor.fetchone()
    return student, teacher


def delete_user(userid, role):
    with p.connect(conn_str) as connection:
        cursor = connection.cursor()
        if role == 'student':
            cursor.execute('SELECT TenSinhVien FROM SinhVien WHERE MaSinhVien = ?', (userid,))
            username = cursor.fetchone()
            cursor.execute("DELETE FROM SinhVien WHERE MaSinhVien = ?", (userid,))
        elif role == 'teacher':
            cursor.execute('SELECT TenGiaoVien FROM GiaoVien WHERE MaGiaoVien = ?', (userid,))
            username = cursor.fetchone()
            cursor.execute("DELETE FROM GiaoVien WHERE MaGiaoVien = ?", (userid,))

        connection.commit()
    return username[0] if username else None


def remove_user_image_folder(username, userid):
    user_image_folder = os.path.join('static/faces', f"{username}_{userid}")
    if os.path.exists(user_image_folder):
        shutil.rmtree(user_image_folder)
        print(f"Deleted folder: {user_image_folder}")
    else:
        print(f"Folder {user_image_folder} not found.")


@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    # if not session['logged_in']:
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_from_db(username, password)

        if user:
            session['logged_in'] = True
            UId = user.UserID
            name = get_student_or_teacher(UId)
            session['name'] = name

            if 'AD' in UId:
                return redirect('/admin')
            elif 'SV' in UId:
                return redirect('/student')
            elif 'GV' in UId:
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
            ID, DateTime, MaMH, MaPH, l = extract_attendance()
            subjects = load_subjects()
            attendance_data = get_attendance_data()
            return render_template('attendance.html', ID=ID, DateTime=DateTime, MaMH=MaMH, MaPH=MaPH, l=l,
                                   totalreg=totalreg(), datetoday2=datetoday2, subjects=subjects,
                                   attendance_data=attendance_data,
                                   mess='Please select a subject.')

        # Bắt đầu quá trình điểm danh với môn học đã chọn
        ID, DateTime, MaMH, MaPH, l = extract_attendance()
        subjects = load_subjects()
        attendance_data = get_attendance_data()
        if 'face_recognition_model.pkl' not in os.listdir('static'):
            return render_template('attendance.html', ID=ID, DateTime=DateTime, MaMH=MaMH, MaPH=MaPH, l=l,
                                   totalreg=totalreg(), datetoday2=datetoday2, subjects=subjects,
                                   attendance_data=attendance_data,
                                   mess='There is no trained model in the static folder. Please add a new face to continue.')

        ret = True
        cap = cv2.VideoCapture(0)
        while ret:
            ret, frame = cap.read()
            if len(extract_faces(frame)) > 0:
                (x, y, w, h) = extract_faces(frame)[0]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (86, 32, 251), 1)
                cv2.rectangle(frame, (x, y), (x + w, y - 40), (86, 32, 251), -1)
                face = cv2.resize(frame[y:y + h, x:x + w], (50, 50))
                identified_person = identify_face(face.reshape(1, -1))[0]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 1)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (50, 50, 255), 2)
                cv2.rectangle(frame, (x, y - 40), (x + w, y), (50, 50, 255), -1)
                cv2.putText(frame, f'{identified_person}', (x, y - 15), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (50, 50, 255), 1)
            # Resize the frame to fit the orange field
            resized_frame = cv2.resize(frame, (640, 480))
            # Display the resized frame on the orange field
            imgBackground[162:162 + 480, 55:55 + 640] = resized_frame
            cv2.imshow('Attendance', imgBackground)
            cv2.setWindowProperty('Attendance', cv2.WND_PROP_TOPMOST, 1)
            if cv2.waitKey(1) == ord('q'):
                break
        add_attendance(identified_person, selected_subject)
        cap.release()
        cv2.destroyAllWindows()
        subjects = load_subjects()
        return render_template('attendance.html', totalreg=totalreg(), datetoday2=datetoday2, subjects=subjects)
    elif request.method == 'GET':
        # Xử lý khi hiển thị giao diện lần đầu
        subjects = load_subjects()
        return render_template('attendance.html', totalreg=totalreg(), datetoday2=datetoday2, subjects=subjects)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    session['Aname'] = "Admin"
    welcome_message = f"Xin chào {session['Aname']}!"
    return render_template('Menu_admin.html', totalreg=totalreg(), welcome_message=welcome_message)


@app.route('/student', methods=['GET', 'POST'])
def student():
    welcome_message = f"Xin chào Sinh viên {session['name']}!"
    subjects = load_subjects()
    return render_template('attendance.html',
                           totalreg=totalreg(),
                           datetoday2=datetoday2, subjects=subjects,
                           welcome_message=welcome_message)


@app.route('/teacher', methods=['GET', 'POST'])
def teacher():
    return redirect('/find')


@app.route('/find', methods=['GET', 'POST'])
def find():
    welcome_message = f"Xin chào Giáo viên {session['name']}!"
    return render_template('find.html', welcome_message=welcome_message)


@app.route('/modify', methods=['GET', 'POST'])
def modify():
    return render_template('modifyUser_Main.html')


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
        addStudentRaw(newusername, newuserid)
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
        username = request.form['username']
        userid = request.form['userid']
        Connection = p.connect(conn_str)
        Cursor_call = Connection.cursor()
        userimagefolder = 'static/faces/' + username + '_' + userid
        if not os.path.isdir(userimagefolder):
            os.makedirs(userimagefolder)
        i, j = 0, 0
        cap = cv2.VideoCapture(0)
        while 1:
            _, frame = cap.read()
            faces = extract_faces(frame)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 20), 2)
                cv2.putText(frame, f'Images Captured: {i}/{nimgs}', (30, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 20), 2, cv2.LINE_AA)
                if j % 5 == 0:
                    name = newusername + '_' + str(i) + '.jpg'
                    cv2.imwrite(userimagefolder + '/' + name, frame[y:y + h, x:x + w])
                    i += 1
                j += 1
            if j == nimgs * 5:
                break
            cv2.imshow('Adding new User', frame)
            if cv2.waitKey(1) == 27:
                break
        cap.release()
        cv2.destroyAllWindows()
        print('Training Model')
        train_model()
        ID, DateTime, MaMH, MaPH, l = extract_attendance()
        subjects = load_subjects()
        attendance_data = get_attendance_data()
        return render_template('attendance.html', ID=ID, DateTime=DateTime, MaMH=MaMH, MaPH=MaPH, l=l,
                               totalreg=totalreg(),
                               datetoday2=datetoday2, subjects=subjects, attendance_data=attendance_data)
    return render_template('attendance.html', ID=ID, DateTime=DateTime, MaMH=MaMH, MaPH=MaPH, l=l, totalreg=totalreg(),
                           datetoday2=datetoday2, subjects=subjects, attendance_data=attendance_data)


@app.route('/modify/remove', methods=['GET', 'POST'])
def remove():
    if request.method == 'POST':
        userid = request.form['userid']
        print(userid)
        session['userid'] = userid
        print(session['userid'])
        student, teacher = get_user_info(userid)

        if student:
            session['role'] = 'student'
            return redirect(url_for('confirm'))
        elif teacher:
            session['role'] = 'teacher'
            return redirect(url_for('confirm'))

        return render_template('modifyUser_Remove.html')

    return render_template('modifyUser_Remove.html')


@app.route('/modify/confirm', methods=['GET', 'POST'])
def confirm():


    if request.method == 'POST':
        role = session['role']
        userid = session['userid']
        username = delete_user(userid, role)

        if request.form.get('confirm') == 'Yes':
            remove_user_image_folder(username, userid)

            # Clean up session
            session.pop('userid', None)
            session.pop('role', None)
            train_model()
            return "User deleted successfully."

        return redirect(url_for('modify_user'))
    userid = session['userid']
    student, teacher = get_user_info(userid)
    return render_template('confirm.html', teacher=teacher, student=student)


@app.route('/modify/changing', methods=['GET', 'POST'])
def changing():
    return render_template('pick.html', teacher=teacher, student=student)


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

        start_date = request.form['start']
        end_date = request.form['end']

        if not start_date or not end_date:
            error = "Please choose both start and end dates."
            return render_template('find_Attendance.html', error=error)

        try:
            Cursor_call.execute(query, (start_date, end_date))
            attendance = Cursor_call.fetchall()
            Connection.close()

            return render_template('attendanceTable.html', attendance=attendance)

        except Exception as e:
            error = f"An error occurred: {str(e)}"
            return render_template('find_Attendance.html', error=error)

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
