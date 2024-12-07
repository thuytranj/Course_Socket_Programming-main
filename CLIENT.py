from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QTreeView, QVBoxLayout, QInputDialog, \
    QLabel, QStyledItemDelegate, QStyleOptionButton, QStyle
from PyQt6.QtCore import QThread, pyqtSignal, QRect, Qt, QEvent
from PyQt6.QtGui import QFileSystemModel, QFont, QStandardItemModel, QStandardItem, QFontMetrics
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
    file_selection_signal = pyqtSignal(list) 

    def __init__(self, client_socket, filePath, mode, downloadDestination = None):
        super(FileTransferThread, self).__init__()
        self.client_socket = client_socket
        self.filePath = filePath
        self.mode = mode
        self.selected_file_index = None
        if downloadDestination is None:
            self.downloadDestination = filePath
        else:
            self.downloadDestination = downloadDestination

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

    def download_folder(self):
        try:
            fileName = os.path.basename(self.filePath)
            message = f"DOWNLOADFOLDER|{fileName}"
            self.client_socket.send(message.encode("utf-8"))

            # Nhận phản hồi đầu tiên từ server
            response = self.recv_full_message(self.client_socket).split('|')
            if response[0] == "ERROR":
                self.error_signal.emit(response[1])
                return
            elif response[0] == "MULTIPLE":
                # Nếu có nhiều file, hiển thị cho người dùng chọn file
                files = response[1:]
                self.file_selection_signal.emit(files)
                while self.selected_file_index is None:
                    QThread.msleep(100)  # Chờ người dùng chọn file
                self.client_socket.send(str(self.selected_file_index).encode("utf-8"))
                # Nhận phản hồi kích thước file sau khi đã chọn file
                response = self.recv_full_message(self.client_socket).split('|')

            if response[0] == "OK":
                # Nếu chỉ có một file, trực tiếp tải file
                fileSize = int(response[1])
                received = 0
                with open(self.downloadDestination, "wb") as f:
                    while received < fileSize:
                        data = self.client_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress_signal.emit(received, fileSize)  # Cập nhật tiến trình
                print(f"File '{self.downloadDestination}' đã tải thành công")
                self.finished.emit()
                return
            else:
                self.error_signal.emit("Lỗi khi tải file")
        except Exception as e:
            self.error_signal.emit(f"Lỗi trong download_file: {str(e)}")

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
                self.file_selection_signal.emit(files)
                while self.selected_file_index is None:
                    QThread.msleep(100)  # Chờ người dùng chọn file
                self.client_socket.send(str(self.selected_file_index).encode("utf-8"))
                # Nhận phản hồi kích thước file sau khi đã chọn file
                response = self.recv_full_message(self.client_socket).split('|')

            if response[0] == "OK":
                # Nếu chỉ có một file, trực tiếp tải file
                fileSize = int(response[1])
                received = 0
                with open(self.downloadDestination, "wb") as f:
                    while received < fileSize:
                        data = self.client_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        self.progress_signal.emit(received, fileSize)  # Cập nhật tiến trình
                print(f"File '{self.downloadDestination}' đã tải thành công")
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
            if not chunk:
                break
            data += chunk
        return data.decode('utf-8').replace(delimiter, "")
    
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


class ButtonDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.button_clicked_callback = None

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() == 1:
            button_style_option = QStyleOptionButton()
            button_style_option.rect = self.get_button_rect(option)
            button_style_option.state |= QStyle.StateFlag.State_Enabled
            button_style_option.text = "Download"

            font = QFont()
            font.setBold(True)
            font.setPointSize(10)

            # Replace fontMetrics assignment with creating a QFontMetrics object
            button_style_option.fontMetrics = QFontMetrics(font)

            QApplication.style().drawControl(QStyle.ControlElement.CE_PushButton, button_style_option, painter)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(size.height() + 40)
        return size

    def get_button_rect(self, option):
        rect = option.rect
        button_width = 100
        button_height = 30
        button_x = rect.right() - button_width - 10
        button_y = rect.center().y() - button_height // 2
        return QRect(button_x, button_y, button_width, button_height)

    def editorEvent(self, event, model, option, index):
        # In PyQt6, use QEvent.Type for event type comparison
        if event.type() == QEvent.Type.MouseButtonRelease:
            rect = self.get_button_rect(option)
            if rect.contains(event.pos()):
                if self.button_clicked_callback:
                    self.button_clicked_callback(index)  # Call the callback without expecting a return
                return True
        return False


def build_tree(data):
    """Build tree model from file paths and sizes."""
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Name", "Size"])

    for entry in data:
        path, size = entry.split(":")
        size = int(size)

        parts = path[2:].split("\\")
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

class Client_w (QMainWindow):
    def __init__ (self, client_socket, list_files):
        super(Client_w, self).__init__()
        uic.loadUi('client.ui', self)
        self.client_socket = client_socket
        self.progress_window = ProgressBar()
        self.list_files = list_files
        self.root_path = '.'

        # Variables
        self.upload_thread = None
        self.download_thread = None

        layout = QVBoxLayout(self.space)
        self.tree_view = QTreeView(self)

        model = build_tree(self.list_files)
        self.tree_view.setModel(model)
        layout.addWidget(self.tree_view)

        button_delegate = ButtonDelegate(self.tree_view)
        button_delegate.button_clicked_callback = self.on_button_clicked
        self.tree_view.setItemDelegateForColumn(1, button_delegate)

        self.tree_view.setColumnWidth(0, 400)
        self.tree_view.setColumnWidth(1, 150)

        self.tree_view.expandAll()

        # Buttons
        self.fileUpload.clicked.connect(self.uploadFile)
        self.fileDownload.clicked.connect(self.downloadFile)
        self.folderUpload.clicked.connect(self.uploadFolder)
        self.folderDownload.clicked.connect(self.downloadFolder)

    def on_button_clicked(self, index):
        """
        Handle the button click event and start the download (or any other logic).

        Args:
            index (QModelIndex): The index of the clicked item in the tree.
        """
        model = index.model()
        parent_index = index.parent()

        # Get the file name from the first column (index.column() == 0)
        file_name_index = index.sibling(index.row(), 0)  # Get the item in the first column (file name)
        file_name = file_name_index.data()

        # Get the size from the second column (index.column() == 1), if you need it
        size_index = index.sibling(index.row(), 1)  # Get the item in the second column (size)
        size = size_index.data()

        # Get the folder path from the parent index, if available
        if not parent_index.isValid():
            # Root folder (no parent)
            download_path = os.path.join(self.root_path, file_name)
        else:
            # File inside a folder
            folder_path = parent_index.data() if parent_index.isValid() else ''
            download_path = os.path.join(self.root_path, folder_path, file_name)

        print(f"Perfome download: {file_name}")
        if "." in file_name:
            self.downloadFile(file_name)
        else:
            self.download_folder(file_name)

    def uploadFile(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "Upload File", "", "All Files (*)")
        if filePath:
            self.upload_thread = FileTransferThread(self.client_socket, filePath, "UPLOAD")
            self.upload_thread.error_signal.connect(self.show_error_message)
            self.upload_thread.progress_signal.connect(self.progress_window.update_progress)
            self.upload_thread.finished.connect(self.transfer_complete)
            self.upload_thread.start()
            self.progress_window.show()

    def download_folder(self, fileOrigin):
        filePath, _ = QFileDialog.getSaveFileName(self, "Download File", "", "All Files (*)")

        if filePath:
            if fileOrigin:
                destinationDownload = filePath
                filePath = fileOrigin

            self.download_thread = FileTransferThread(self.client_socket, filePath, "DOWNLOADFOLDER", destinationDownload)
            self.download_thread.error_signal.connect(self.show_error_message)
            self.download_thread.progress_signal.connect(self.progress_window.update_progress)

            # Tín hiệu hoàn thành
            self.download_thread.finished.connect(self.transfer_complete)
            self.download_thread.file_selection_signal.connect(self.show_file_selection_dialog)

            # Tín hiệu lỗi để ngắt kết nối nếu có lỗi
            self.download_thread.error_signal.connect(self._on_error)

            self.download_thread.start()
            self.progress_window.show()

    def downloadFile(self, fileOrigin = None):
        filePath, _ = QFileDialog.getSaveFileName(self, "Download File", "", "All Files (*)")

        if filePath:
            if fileOrigin:
                destinationDownload = filePath
                filePath = fileOrigin
            else:
                destinationDownload = None

            self.download_thread = FileTransferThread(self.client_socket, filePath, "DOWNLOAD", destinationDownload)
            self.download_thread.error_signal.connect(self.show_error_message)
            self.download_thread.progress_signal.connect(self.progress_window.update_progress)

            # Tín hiệu hoàn thành
            self.download_thread.finished.connect(self.transfer_complete)
            self.download_thread.file_selection_signal.connect(self.show_file_selection_dialog)
            
            # Tín hiệu lỗi để ngắt kết nối nếu có lỗi
            self.download_thread.error_signal.connect(self._on_error)

            self.download_thread.start()
            self.progress_window.show()

    def downloadFolder (self):
        # to do
        pass
    
    def _on_error(self, error_message):
        """Ngắt kết nối tín hiệu progress_signal và finished khi có lỗi"""
        self.download_thread.finished.disconnect(self.transfer_complete)
        self.download_thread.progress_signal.disconnect(self.progress_window.update_progress)

        # Ẩn thanh tiến trình
        self.progress_window.hide()  

    def show_file_selection_dialog(self, files):
        self.progress_window.hide()
        selected_file, ok = QInputDialog.getItem(
            self,
            "Select File",
            "Multiple files found. Please select:",
            files,
            0,
            False
        )
        if ok and selected_file:
            selected_index = files.index(selected_file)
            self.download_thread.selected_file_index = selected_index
            self.progress_window.show()
        else:
            self.download_thread.error_signal.emit("File selection canceled")

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
    def __init__ (self, client_socket, list_files):
        super(MainApp, self).__init__()
        self.client_socket = client_socket

        self.login_w = Login_w(client_socket, self.switch_window)
        self.signup_w = SignUp_w(client_socket, self.switch_window)
        self.client_w = Client_w(client_socket, list_files)

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
    PORT=10035

    try:
        client_socket = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect ((IP, PORT))
        client_socket.send(b"VIEWFOLDER")
        response = client_socket.recv(4096).decode()
        print(response)
    except Exception as e:
        print ("Cannot connect to server")
        sys.exit()

    app = QApplication(sys.argv)
    main_app = MainApp(client_socket, response.split('$'))
    main_app.show()
    sys.exit(app.exec())