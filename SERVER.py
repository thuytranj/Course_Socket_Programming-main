from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QFileSystemModel
import sys
import socket
import os
import shutil
import threading
import time
import zipfile

SERVER_FOLDER = "./ServerStorage"
USER_DATA_FILE = "./user.txt"
clients = []  # Danh sách lưu thông tin client

def handle_client (client_socket, address):
    print (f"Đã kêt nối với client: {address}")
    
    client_info = {
        "address": address,
        "status" : "Connected",
        "connected_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    clients.append(client_info)

    while True:
        try:
            command=client_socket.recv (4096).decode ('utf-8').strip()
            if not command:
                break
            parts = command.split('|')
            print (parts)

            if parts[0]=="LOGIN":
                handle_login (client_socket, parts[1], parts[2])
            elif parts[0]=="SIGNUP":
                handle_signup (client_socket, parts[1], parts[2])
            elif parts[0]=="UPLOAD":
                receive_file (client_socket, parts[1], int (parts[2]))
            elif parts[0]=="DOWNLOAD":
                send_file (client_socket, parts[1])
            elif parts[0]=="UPLOADFOLDER":
                receive_folder (client_socket, parts[1], int (parts[2]))
            elif parts[0]=="VIEWFOLDER":
                get_file(client_socket)
            else: 
                print ("Unknown command")
                client_socket.send (b"ERROR: Unknown command.")
        except Exception as e:
            print (f"Lỗi khi xử lý client: {str(e)}")
            break
    client_info["status"] = "Disconnected"
    print (f"Đã ngắt kết nối với client: {address}")
    client_socket.close()

def handle_login(client_socket, username, password):
    users = load_users ()

    if username in users and password == users [username]:
        client_socket.send (b"OK")
        print (f"client '{username}' đăng nhập thành công")
    else:
        client_socket.send (b"ERROR")
        print (f"client '{username}' đăng nhập thất bại")

def handle_signup (client_socket, username, password):
    users = load_users ()
    if username in users:
        client_socket.send (b"ERROR")
        print (f"client '{username}' đã tồn tại")
    else:
        users[username] = password
        save_users (users)
        client_socket.send (b"OK")
        print (f"client '{username}' đã đăng ký thành công")

def get_file(client_socket):
    list_files = []
    for root, dirs, files in os.walk(SERVER_FOLDER):
        for file in files:
            full_path = os.path.join(root, file)
            size = os.path.getsize(full_path)
            name = os.path.join(root.replace(SERVER_FOLDER,'.'), file)
            list_files.append(name + ":" + str(size))
    result = ', '.join(list_files)
    client_socket.send (result.encode())
def ZipFolder(folder_path,output_path):
    try:
        with az.Archive() as archive:
            archive.create_entries(folder_path)
            archive.save(output_path)
    except Exception as e:
        print(f"Error while zipping folder: {e}")
def receive_file (client_socket, fileName, fileSize):
    try:
        # Tạo một hậu tố duy nhất bằng timestamp
        timestamp = int(time.time())  # Sử dụng thời gian hiện tại làm hậu tố
        uniqueFileName = f"{timestamp}_{fileName}"

        os.makedirs (SERVER_FOLDER, exist_ok=True)
        filePath=os.path.join (SERVER_FOLDER, uniqueFileName)

        if os.path.exists (filePath):
            client_socket.send (f"ERROR".encode('utf-8'))
            print (f"file '{fileName}' đã tồn tại")
            return
        
        client_socket.send (f"OK".encode('utf-8'))
        with open (filePath, "wb") as f:
            received=0
            while received < fileSize:
                data = client_socket.recv (4096)
                f.write (data)
                received += len (data)

    except Exception as e:
        print (f"Lỗi khi nhận file: {str(e)}")
def receive_folder (client_socket, folderName, folderSize):
    try:
        os.makedirs (SERVER_FOLDER, exist_ok=True)
        filePath=os.path.join (SERVER_FOLDER, folderName)
        if os.path.exists (filePath):
            client_socket.send (f"ERROR".encode('utf-8'))
            print (f"file '{folderName}' đã tồn tại")
            return
        
        client_socket.send (f"OK".encode('utf-8'))
        with open (filePath, "wb") as f:
            received=0
            while received < folderSize:
                data = client_socket.recv (4096)
                f.write (data)
                received += len (data)

        try:
            # Tạo đường dẫn thư mục đích (dựa trên tên file ZIP, bỏ phần mở rộng)
            folder_name = os.path.splitext(os.path.basename(filePath))[0]  # Lấy tên file ZIP, bỏ đuôi .zip
            folder_path = os.path.join(SERVER_FOLDER, folder_name)
            
            # Tạo thư mục nếu chưa tồn tại
            os.makedirs(folder_path, exist_ok=True)
            with zipfile.ZipFile(filePath, 'r') as zip_ref:
                zip_ref.extractall(folder_path)
            print(f"Extracted {filePath} successfully.")
            os.remove(filePath)  # Xóa file ZIP sau khi giải nén
        except zipfile.BadZipFile:
            print("Received file is not a valid ZIP file")
    except Exception as e:
        print (f"Lỗi khi nhận file: {str(e)}")

def send_file (client_socket, fileName):
    try:
        # Tìm kiếm file trong SERVER_FOLDER và tất cả thư mục con
        filePath = None
        for root, dirs, files in os.walk(SERVER_FOLDER):
            if fileName in files:
                filePath = os.path.join(root, fileName)
                break

        # Kiểm tra nếu file không tồn tại
        if filePath is None:
            client_socket.send(f"ERROR".encode('utf-8'))
            print(f"File '{fileName}' không tồn tại trong {SERVER_FOLDER}")
            return
        
        fileSize = os.path.getsize (filePath)
        message = f"OK|{fileSize}"
        client_socket.send (message.encode ('utf-8'))
        
        with open(filePath, "rb") as f:
            sent = 0
            while True:
                data = f.read(4096)
                if not data:
                    break
                client_socket.sendall(data)
                sent += len(data)
    except Exception as e:
        print (f"Lỗi khi gửi file: {str(e)}")
def load_users ():
    users = {}
    if os.path.isfile (USER_DATA_FILE):
        with open (USER_DATA_FILE, "r") as f:
            for line in f:
                username, password = line.strip().split("|")
                users[username] = password
    return users

def save_users (users):
    with open (USER_DATA_FILE, "w") as f:
        for username, password in users.items():
            f.write (f"{username}|{password}\n")

class Server_w (QMainWindow):
    def __init__ (self):
        super().__init__()
        uic.loadUi("server.ui", self)

        self.clientsInfo.clicked.connect(self.client_info)
        self.serverStorage.clicked.connect(self.server_storage)

        # Chạy server trong một luồng riêng
        self.server_thread = ServerThread("localhost", 10034)
        self.server_thread.start()

        # Ẩn TreeView lúc đầu
        self.treeView.hide()

        # Tạo QTimer để cập nhật bảng tự động
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_client_table)
        self.timer.start(2000)  # Cập nhật mỗi 2 giây
    def update_client_table (self):
        # Tạo bảng để hiển thị thông tin client
        self.tableWidget.setRowCount(len(clients))
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["Address", "Status", "Connected Time"])

        # Thiết lập kích thước cho từng cột
        self.tableWidget.setColumnWidth(0, 250)  # Cột "Address" rộng 150 pixel
        self.tableWidget.setColumnWidth(1, 150)  # Cột "Status" rộng 100 pixel
        self.tableWidget.setColumnWidth(2, 225)  # Cột "Connected Time" rộng 200 pixel

        for row, client in enumerate(clients):
            # Điền thông tin của từng client vào bảng
            self.tableWidget.setItem(row, 0, QTableWidgetItem(str(client["address"])))
            self.tableWidget.setItem(row, 1, QTableWidgetItem(client["status"]))
            self.tableWidget.setItem(row, 2, QTableWidgetItem(client["connected_time"]))

    def client_info(self):
        # Hiển thị TableWidget và ẩn TreeView
        self.tableWidget.show()
        self.treeView.hide()

        self.update_client_table()

    def server_storage(self):
        # Hiển thị TreeView và ẩn TableWidget
        self.treeView.show()
        self.tableWidget.hide()

        # Hiển thị danh sách file và folder trong SERVER_FOLDER
        self.model = QFileSystemModel()
        self.model.setRootPath(SERVER_FOLDER)
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(SERVER_FOLDER))

        # Đặt chế độ tự động điều chỉnh kích thước cho tất cả cột
        self.treeView.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

class ServerThread(QThread):
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.ip, self.port))
        server.listen()
        print(f"Server đang lắng nghe tại {self.ip}:{self.port}")
        while True:
            client_socket, address = server.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, address))
            client_thread.start()

if __name__ == "__main__":

    os.makedirs (SERVER_FOLDER, exist_ok=True)

    app = QApplication(sys.argv)
    window = Server_w()
    window.show()
    sys.exit(app.exec())
