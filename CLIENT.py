from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QInputDialog, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import  QStandardItemModel, QStandardItem
import sys
import socket
import os
import shutil
import threading

# ========== Login Window ==========
class Login_w (QMainWindow):
    def __init__(self, client_socket, switch_window):
        super(Login_w, self).__init__()
        uic.loadUi('login.ui', self)
        self.client_socket = client_socket
        self.switch_window = switch_window

        # Buttons
        self.loginbutton.clicked.connect(self.handle_login)
        self.Register.clicked.connect(lambda: self.switch_window(1))  # Chuyển sang giao diện đăng ký

    def handle_login (self):
        userName=self.username.text()
        password=self.password.text()
        
        if not userName or not password:
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")
            return

        try:
            message = f"LOGIN|{userName}|{password}"
            self.client_socket.send(message.encode('utf-8'))

            # Nhận thông điệp đăng nhập thành công
            response = self.client_socket.recv(1024).decode()
            if response == "OK":
                self.switch_window(2)  # Chuyển sang giao diện chính
            else:
                QMessageBox.warning(self, "Login Error", "Invalid username or password.")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Error: {str(e)}")


# ========== Sign-Up Window ==========
class SignUp_w (QMainWindow):
    def __init__(self, client_socket, switch_window):
        super(SignUp_w, self).__init__()
        uic.loadUi('register.ui', self)
        self.client_socket = client_socket
        self.switch_window = switch_window

        # Buttons
        self.register_3.clicked.connect(self.handle_signup)
        self.Back.clicked.connect(lambda: self.switch_window(0))  # Chuyển sang giao diện đăng nhập

    def handle_signup (self):
        userName=self.username.text()
        password=self.password.text()
        confirmPassword=self.confirm_password.text()

        if not userName or not password or not confirmPassword:
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")
            return

        if password == confirmPassword:
            try:
                message = f"SIGNUP|{userName}|{password}"
                self.client_socket.send(message.encode('utf-8'))

                # Nhận thông điệp đăng ký thành công
                response = self.client_socket.recv(4096).decode()
                if response == "OK":
                    QMessageBox.information(self, "Success", "Account created successfully.")
                    self.switch_window(0)  # Chuyển sang giao diện đăng nhập
                else:
                    QMessageBox.warning (self, "Error", "Account already exists.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
        else:
            QMessageBox.warning(self, "Password Error", "Passwords do not match.")

# ========== Progress Bar ==========
class ProgressBar(QMainWindow):
    def __init__(self):
        super(ProgressBar, self).__init__()
        uic.loadUi('progress_bar.ui', self)
        
        # Tìm đối tượng QLabel với tên 'labelProgress' trong giao diện
        self.labelProgress = self.findChild(QLabel, 'labelProgress')
        
        # Đặt giá trị mặc định cho thanh tiến trình
        self.progressBar.setValue(0)

    def update_progress(self, current, total):
        if total == 0:
            return
        percent = int(current * 100 / total)
        self.progressBar.setValue(percent)
        
        # Cập nhật phần trăm vào QLabel
        self.labelProgress.setText(f"{percent}% Completed")


class FileTransferThread(QThread):
    progress_signal = pyqtSignal(int, int)  # Signal: current, total
    finished = pyqtSignal()  # Emits when transfer completes
    error_signal = pyqtSignal(str)  # Signal to emit error message
    file_selection_signal = pyqtSignal(list, str) 

    def __init__(self, client_socket, filePath="", mode="", folderName=""):
        super(FileTransferThread, self).__init__()
        self.client_socket = client_socket
        self.filePath = filePath
        self.mode = mode
        self.folderName = folderName
        self.selected_file_index = None  

    def run(self):
        try:
            if self.mode == "UPLOAD":
                self.upload_file()
            elif self.mode == "DOWNLOAD":
                self.download_file()
            elif self.mode == "UPLOADFOLDER":
                self.upload_folder()
            elif self.mode == "DOWNLOADFOLDER":
                self.download_folder()
        except Exception as e:
            self.error_signal.emit(f"Error in File Transfer Thread: {e}")
            print(f"Error in File Transfer Thread: {e}")

    def upload_file(self):
        try:
            fileName = os.path.basename(self.filePath)
            fileSize = os.path.getsize(self.filePath)
            self.client_socket.send(f"UPLOAD|{fileName}|{fileSize}".encode("utf-8"))

            response = self.client_socket.recv(4096).decode()
            if response == "OK":
                with open(self.filePath, "rb") as f:
                    sent = 0
                    while True:
                        data = f.read(4096)
                        if not data:
                            break
                        self.client_socket.sendall(data)
                        sent += len(data)
                        self.progress_signal.emit(sent, fileSize)  # Emit progress
                self.finished.emit()
            else:
                print(response)
                print("File upload error")
                self.error_signal.emit("File upload error")
        except Exception as e:
            self.error_signal.emit(f"Error in upload_file: {str(e)}")
            print(f"Error in upload_file: {str(e)}")
    
    def download_file(self):
        try:
            fileName = os.path.basename(self.filePath)
            message = f"DOWNLOAD|{fileName}"
            self.client_socket.send(message.encode("utf-8"))

            # Nhận phản hồi đầu tiên từ server
            response = self.recv_full_message(self.client_socket).split('|')
            if response[0] == "ERROR":
                self.error_signal.emit(response[1])
                return
            elif response[0] == "MULTIPLE":
                # Nếu có nhiều file, hiển thị cho người dùng chọn file
                files = response[1:]
                self.file_selection_signal.emit(files, "Files")
                while self.selected_file_index is None:
                    QThread.msleep(3)  # Chờ người dùng chọn file
                self.client_socket.send(str(self.selected_file_index).encode("utf-8"))
                # Nhận phản hồi kích thước file sau khi đã chọn file
                response = self.recv_full_message(self.client_socket).split('|')

            if response[0] == "OK":
                # Nếu chỉ có một file, trực tiếp tải file
                fileSize = int(response[1])
                received = 0

                with open(self.filePath, "wb") as f:
                    while received < fileSize:
                        data = self.client_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress_signal.emit(received, fileSize)  # Cập nhật tiến trình
                print(f"File '{self.filePath}' đã tải thành công")
                self.finished.emit()
                return
            else:
                self.error_signal.emit("Lỗi khi tải file")
        except Exception as e:
            self.error_signal.emit(f"Lỗi trong download_file: {str(e)}")

    

    def recv_full_message(self, socket, delimiter="||END||"):
        data = b""
        while delimiter.encode() not in data:
            chunk = socket.recv(1024)
            if not chunk:  # Nếu không nhận được dữ liệu
                break
            data += chunk
            
        if len(data) == 0:
            raise Exception("No data received from server")
            
        try:
            decoded_data = data.decode('utf-8').replace(delimiter, "")
            return decoded_data
        except UnicodeDecodeError:
            # Nếu không thể giải mã, trả về dữ liệu gốc dưới dạng byte (dành cho file hoặc dữ liệu nhị phân)
            return data

    
    def upload_folder(self):
        try:
            fileName = os.path.basename(self.filePath)
            fileSize = os.path.getsize(self.filePath)
            self.client_socket.send(f"UPLOADFOLDER|{fileName}|{fileSize}".encode("utf-8"))

            response = self.client_socket.recv(4096).decode()
            if response == "OK":
                with open(self.filePath, "rb") as f:
                    sent = 0
                    while True:
                        data = f.read(4096)
                        if not data:
                            break
                        self.client_socket.sendall(data)
                        sent += len(data)
                        self.progress_signal.emit(sent, fileSize)  # Emit progress
                self.finished.emit()
            else:
                print(response)
                self.error_signal.emit("Folder upload error")
                print("Folder upload error")
        except Exception as e:
            self.error_signal.emit(f"Error in upload_folder: {str(e)}")
            print(f"Error in upload_foler: {str(e)}")

    def download_folder(self):
        try:
            # Đặt đường dẫn thư mục Download mặc định
            download_folder = os.path.expanduser('~') + '/Downloads' 

            # Gửi yêu cầu tải thư mục tới server
            self.client_socket.sendall(f"DOWNLOADFOLDER|{self.folderName}".encode("utf-8"))

            response = self.client_socket.recv(1024).decode('utf-8').split('|')
            print (response)

            if response[0] == "ERROR":
                self.error_signal.emit(response[1])
                return

            elif response[0] == "MULTIPLE":
                # Nếu có nhiều thư mục, cho người dùng chọn
                folders = response[1:]
                self.file_selection_signal.emit(folders, "Folders")
                while self.selected_file_index is None:
                    QThread.msleep(3)  # Chờ người dùng chọn thư mục
                self.client_socket.send(str(self.selected_file_index).encode("utf-8"))
                response = self.client_socket.recv(1024).decode('utf-8').split('|')
                print (response)

            if response[0] == "OK":
                print (response)
                self.progress_signal.emit(0, 100)  

                # Nhận kích thước thư mục từ server
                folder_size = int(response[1])  # Kích thước thư mục (dưới dạng bytes)
                received = 0

                # Đảm bảo thư mục tải về sẽ được lưu vào Downloads
                target_folder_path = os.path.join(download_folder, self.folderName)

                # Tiến hành nhận file zip và lưu vào thư mục Downloads
                with open(f"{target_folder_path}.zip", "wb") as f:
                    while received < folder_size:
                        data = self.client_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress_signal.emit(received, folder_size)  # Cập nhật tiến trình

                print(f"Folder '{self.folderName}' đã tải thành công tại {target_folder_path}")
                self.finished.emit()
            else:
                self.error_signal.emit("Lỗi khi tải thư mục")
        except Exception as e:
            self.error_signal.emit(f"Error in download_folder: {str(e)}")
            print(f"Error in download_folder: {str(e)}")

class Client_w (QMainWindow):
    def __init__ (self, client_socket):
        super(Client_w, self).__init__()
        uic.loadUi('client.ui', self)
        self.client_socket = client_socket
        self.progress_window = ProgressBar()

        # Variables
        self.upload_thread = None
        self.download_thread = None

        # Ẩn MenuUpload lúc đầu
        self.MenuUpload.hide()

        # Buttons
        self.fileUpload.clicked.connect(self.uploadFile)
        self.fileDownload.clicked.connect(self.downloadFile)
        self.folderUpload.clicked.connect(self.uploadFolder)
        self.folderDownload.clicked.connect(self.downloadFolder)

        # Tạo QTimer để cập nhật bảng tự động
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.display_files)
        self.timer.start(5000)

    def pause_timer(self):
        if self.timer.isActive():
            self.timer.stop()

    def resume_timer(self):
        if not self.timer.isActive():
            self.timer.start(5000)

    def receive_list(self):
        self.client_socket.send (f"VIEWFOLDER".encode ('utf-8'))
        data = self.client_socket.recv(1024 * 1024).decode('utf-8')
        if data.startswith("OK|"):
            return data[3:].split("|")
        return []

    # Hàm xây dựng cây dữ liệu từ danh sách tệp
    def build_tree(self, file_list):
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Name", "Size"])

        for entry in file_list:
            path, size = entry.split(":")
            size = int(size)

            parts = path.split(os.path.sep)
            current_item = model.invisibleRootItem()

            for part in parts[:-1]:
                match = None
                for i in range(current_item.rowCount()):
                    if current_item.child(i, 0).text() == part:
                        match = current_item.child(i, 0)
                        break
                if not match:
                    match = QStandardItem(part)
                    current_item.appendRow([match, QStandardItem()])
                current_item = match

            file_item = QStandardItem(parts[-1])
            size_item = QStandardItem(f"{size} bytes")
            current_item.appendRow([file_item, size_item])

        return model
    
    def display_files(self):
        # Nhận danh sách tệp từ server
        file_list = self.receive_list()
        
        # Xây dựng cây tệp từ danh sách
        model = self.build_tree(file_list)  # Sử dụng hàm build_tree
        self.treeView.setModel(model)  # Gán mô hình cho QTreeView

        # Điều chỉnh độ rộng cột
        self.treeView.setColumnWidth(0, 750) 
        self.treeView.setColumnWidth(1, 100) 

        self.treeView.expandAll()

    def uploadFile(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "Upload File", "", "All Files (*)")
        if filePath:
            self.pause_timer()  # Tạm dừng cập nhật danh sách file

            self.upload_thread = FileTransferThread(self.client_socket, filePath=filePath, mode="UPLOAD")
            self.upload_thread.error_signal.connect(self.show_error_message)
            self.upload_thread.progress_signal.connect(self.progress_window.update_progress)
            self.upload_thread.finished.connect(self.transfer_complete)
            self.upload_thread.finished.connect(self.resume_timer)  # Kích hoạt lại QTimer sau khi hoàn tất

            self.upload_thread.start()
            self.progress_window.show()

    def downloadFile(self):
        #self.display_files ()
        filePath, _ = QFileDialog.getSaveFileName(self, "Download File", "", "All Files (*)")
        if filePath:
            self.pause_timer()  # Tạm dừng cập nhật danh sách file
            self.download_thread = FileTransferThread(self.client_socket, filePath=filePath, mode="DOWNLOAD")
            self.download_thread.error_signal.connect(self.show_error_message)
            self.download_thread.progress_signal.connect(self.progress_window.update_progress)

            # Tín hiệu hoàn thành
            self.download_thread.finished.connect(self.transfer_complete)
            self.download_thread.file_selection_signal.connect(self.show_file_selection_dialog)
            
            # Tín hiệu lỗi để ngắt kết nối nếu có lỗi
            self.signals_connected = True
            self.download_thread.error_signal.connect(self._on_error)

            self.download_thread.finished.connect(self.resume_timer)  # Kích hoạt lại QTimer sau khi hoàn tất
            self.download_thread.start()
            self.progress_window.show()

    def downloadFolder(self):
        folder_name, ok = QInputDialog.getText(self, "Nhập tên thư mục", "Nhập tên thư mục cần tải:")
        
        if ok and folder_name:
            self.pause_timer()  # Tạm dừng cập nhật danh sách file
            self.download_thread = FileTransferThread(self.client_socket, mode="DOWNLOADFOLDER", folderName=folder_name)
            self.download_thread.error_signal.connect(self.show_error_message)
            self.download_thread.progress_signal.connect(self.progress_window.update_progress)

            self.download_thread.finished.connect(lambda: self.transfer_complete(mode="Folder"))
            self.download_thread.file_selection_signal.connect(self.show_file_selection_dialog)

            self.signals_connected = True
            self.download_thread.error_signal.connect(self._on_error)

            self.download_thread.finished.connect(self.resume_timer)  # Kích hoạt lại QTimer sau khi hoàn tất
            self.download_thread.start()
            self.progress_window.show()

    
    def _on_error(self, error_message):
        """Ngắt kết nối tín hiệu progress_signal và finished khi có lỗi"""
        if hasattr(self, "signals_connected") and self.signals_connected:
            try:
                self.download_thread.finished.disconnect(self.transfer_complete)
                self.download_thread.progress_signal.disconnect(self.progress_window.update_progress)
                self.signals_connected = False
            except TypeError as e:
                print(f"Lỗi khi ngắt kết nối tín hiệu: {e}")
        
        # Ẩn thanh tiến trình
        self.progress_window.hide()
  

    def show_file_selection_dialog(self, list, mode = "Files"):
        self.progress_window.hide()
        selected_file, ok = QInputDialog.getItem(
            self,
            f"Select {mode}",
            f"Multiple {mode} found. Please select:",
            list,
            0,
            False
        )
        if ok and selected_file:
            selected_index = list.index(selected_file)
            self.download_thread.selected_file_index = selected_index
            self.progress_window.show()
        else:
            self.download_thread.error_signal.emit("File selection canceled")

    def uploadFolder (self):
        folderPath = QFileDialog.getExistingDirectory(self, "Select Folder to Upload", "")
        if folderPath:
            try:
                self.pause_timer()  # Tạm dừng cập nhật danh sách file
                folderName = os.path.basename(folderPath.rstrip(os.sep))
                # Tạo đường dẫn cho file ZIP
                zipFilePath = f"{folderName}.zip"
                
                # Nén thư mục thành file ZIP
                shutil.make_archive(folderName, 'zip', folderPath)

                self.upload_thread = FileTransferThread(self.client_socket, filePath=zipFilePath, mode="UPLOADFOLDER")
                self.upload_thread.error_signal.connect(self.show_error_message)
                self.upload_thread.progress_signal.connect(self.progress_window.update_progress)
                self.upload_thread.finished.connect(lambda: self.transfer_complete (mode="Folder"))

                # Bắt sự kiện khi file upload hoàn thành để xóa file ZIP
                self.upload_thread.finished.connect(lambda: self.remove_temp_zip(zipFilePath))

                self.upload_thread.finished.connect(self.resume_timer)  # Kích hoạt lại QTimer sau khi hoàn tất
                self.upload_thread.start()
                self.progress_window.show()
                
            except Exception as e:
                print(f"Error zipping folder: {str(e)}")

    def show_error_message(self, message):
        QMessageBox.warning (self, "Error", message)

    def remove_temp_zip(self, zipFilePath):
        try:
            # Đảm bảo file tồn tại trước khi xóa
            if os.path.exists(zipFilePath):
                os.remove(zipFilePath)
        except Exception as e:
            print(f"Error removing temporary zip file: {str(e)}")

    def transfer_complete (self, mode="File"):
        if self.progress_window:
            self.progress_window.close()  
        QMessageBox.information(self, "Transfer Complete", f"{mode} transfer finished successfully!")

    def closeEvent(self, event):
        try:
            if self.upload_thread and self.upload_thread.isRunning():
                self.upload_thread.wait()
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.wait()
            self.client_socket.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        event.accept()

class MainApp (QtWidgets.QStackedWidget):
    def __init__ (self, client_socket):
        super(MainApp, self).__init__()
        self.client_socket = client_socket

        self.login_w = Login_w(client_socket, self.switch_window)
        self.signup_w = SignUp_w(client_socket, self.switch_window)
        self.client_w = Client_w(client_socket)

        self.addWidget (self.login_w)
        self.addWidget (self.signup_w)
        self.addWidget (self.client_w)

        self.setCurrentIndex (0)
        self.setFixedSize(890, 710) # Cố định khung

    def switch_window (self, index):
        self.setCurrentIndex (index)

if __name__ == "__main__":

    IP='localhost'
    PORT=10048

    try:
        client_socket = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect ((IP, PORT))
    except Exception as e:
        print ("Cannot connect to server")
        sys.exit()

    app = QApplication(sys.argv)
    main_app = MainApp(client_socket)
    main_app.show()
    sys.exit(app.exec())