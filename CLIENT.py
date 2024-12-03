from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox,  QTreeView, QVBoxLayout
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFileSystemModel
import sys
import socket
import os
import shutil
import threading
import zipfile

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
class ProgressBar (QMainWindow):
    def __init__(self):
        super(ProgressBar, self).__init__()
        uic.loadUi('progress_bar.ui', self)
        # Đặt giá trị mặc định cho thanh tiến trình
        self.progressBar.setValue(0)

    def update_progress(self, current, total):
        if total==0:
            return
        percent = int(current * 100 / total)
        self.progressBar.setValue(percent)
        self.progressBar.setFormat(f"{percent}% Completed")


class FileTransferThread(QThread):
    progress_signal = pyqtSignal(int, int)  # Signal: current, total
    finished = pyqtSignal()  # Emits when transfer completes
    error_signal = pyqtSignal(str)  # Signal to emit error message

    def __init__(self, client_socket, filePath, mode):
        super(FileTransferThread, self).__init__()
        self.client_socket = client_socket
        self.filePath = filePath
        self.mode = mode

    def run(self):
        try:
            if self.mode == "UPLOAD":
                self.upload_file()
            elif self.mode == "DOWNLOAD":
                self.download_file()
            elif self.mode == "UPLOADFOLDER":
                self.upload_folder()
            self.finished.emit()
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

            response = self.client_socket.recv(1024).decode("utf-8").split('|')
            if response[0] == "OK":
                fileSize = int (response [1])
                received = 0
                with open(self.filePath, "wb") as f:
                    while received < fileSize:
                        data = self.client_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress_signal.emit(received, fileSize)  # Emit progress updates
                print(f"File '{self.filePath}' downloaded successfully")
            else:
                print (response)
                self.error_signal.emit("File does not exist on server")
                print("File download error")
        except Exception as e:
            self.error_signal.emit(f"Error in download_file: {str(e)}")
            print(f"Error in download_file: {str(e)}")

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
            else:
                print(response)
                self.error_signal.emit("Folder upload error")
                print("Folder upload error")
        except Exception as e:
            self.error_signal.emit(f"Error in upload_folder: {str(e)}")
            print(f"Error in upload_foler: {str(e)}")

class Client_w (QMainWindow):
    def __init__ (self, client_socket):
        super(Client_w, self).__init__()
        uic.loadUi('client.ui', self)
        self.client_socket = client_socket
        self.progress_window = ProgressBar()

        # Variables
        self.upload_thread = None
        self.download_thread = None

        # Buttons
        self.fileUpload.clicked.connect(self.uploadFile)
        self.fileDownload.clicked.connect(self.downloadFile)
        self.folderUpload.clicked.connect(self.uploadFolder)



    def uploadFile(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "Upload File", "", "All Files (*)")
        if filePath:
            self.upload_thread = FileTransferThread(self.client_socket, filePath, "UPLOAD")
            self.upload_thread.error_signal.connect(self.show_error_message)
            self.upload_thread.progress_signal.connect(self.progress_window.update_progress)
            self.upload_thread.finished.connect(self.transfer_complete)
            self.upload_thread.start()
            self.progress_window.show()

    def downloadFile(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "Download File", "", "All Files (*)")
        if filePath:
            self.download_thread = FileTransferThread(self.client_socket, filePath, "DOWNLOAD")
            self.download_thread.error_signal.connect(self.show_error_message)
            self.download_thread.progress_signal.connect(self.progress_window.update_progress)

            # Tín hiệu hoàn thành
            self.download_thread.finished.connect(self.transfer_complete)

            # Cần một tín hiệu lỗi để ngắt kết nối nếu có lỗi
            self.download_thread.error_signal.connect(self._on_error)

            self.download_thread.start()
            self.progress_window.show()
    def _on_error(self, error_message):
        """Ngắt kết nối tín hiệu progress_signal và finished khi có lỗi"""
        self.download_thread.finished.disconnect(self.transfer_complete)
        self.download_thread.progress_signal.disconnect(self.progress_window.update_progress)

        # Ẩn hoặc đóng thanh tiến trình
        self.progress_window.hide()  # Hoặc self.progress_window.close()

    def uploadFolder (self):
        folderPath = QFileDialog.getExistingDirectory(self, "Select Folder to Upload", "")
        if folderPath:
            try:
                folderName = os.path.basename(folderPath.rstrip(os.sep))
                # Tạo đường dẫn cho file ZIP
                zipFilePath = f"{folderName}.zip"
                
                # Nén thư mục thành file ZIP
                shutil.make_archive(folderName, 'zip', folderPath)

                self.upload_thread = FileTransferThread(self.client_socket, zipFilePath, "UPLOADFOLDER")
                self.upload_thread.error_signal.connect(self.show_error_message)
                self.upload_thread.progress_signal.connect(self.progress_window.update_progress)
                self.upload_thread.finished.connect(self.transfer_complete)

                # Bắt sự kiện khi file upload hoàn thành để xóa file ZIP
                self.upload_thread.finished.connect(lambda: self.remove_temp_zip(zipFilePath))

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

    def transfer_complete (self):
        if self.progress_window:
            self.progress_window.close()  
        QMessageBox.information(self, "Transfer Complete", "File/Folder transfer finished successfully!")

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
        self.setFixedHeight (800)
        self.setFixedWidth (1000)

    def switch_window (self, index):
        self.setCurrentIndex (index)

if __name__ == "__main__":

    IP='localhost'
    PORT=10034

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