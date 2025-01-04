import os
import sys
import json
import logging
import subprocess
from pathlib import Path
import requests
import time
from threading import Thread
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QToolBar, 
                            QStatusBar, QMessageBox, QInputDialog, QTreeWidget, 
                            QTreeWidgetItem, QHeaderView, QMenuBar, QMenu,
                            QDialog, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                            QSplitter, QTextEdit, QComboBox, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from config import APP_NAME, ABOUT_TEXT

APP_DIR = os.path.join(str(Path.home()), '.tuxcut')
if not os.path.isdir(APP_DIR):
    os.mkdir(APP_DIR)
    client_log = Path(os.path.join(APP_DIR, 'tuxcut.log'))
    client_log.touch(exist_ok=True)
    client_log.chmod(0o666)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tuxcut-client')
handler = logging.FileHandler(os.path.join(APP_DIR, 'tuxcut.log'))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class ServerThread(Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.process = None
    
    def run(self):
        try:
            server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server', 'server.py')
            python_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.venv', 'bin', 'python')
            
            # Jalankan server dengan output ke terminal
            self.process = subprocess.Popen(
                [python_path, server_path],
                stdout=sys.stdout,
                stderr=sys.stderr,
                bufsize=1,
                universal_newlines=True
            )
            
            # Log start server
            print("\nStarting TuxCut Qt Server...")
            
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            print(f"\nError starting server: {str(e)}")
    
    def stop(self):
        if self.process:
            print("\nStopping TuxCut Qt Server...")
            self.process.terminate()
            self.process.wait()
            print("Server stopped.")

class ScanThread(QThread):
    finished = pyqtSignal(list)
    
    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        
    def run(self):
        try:
            res = requests.get(f'http://127.0.0.1:8013/scan/{self.ip}')
            if res.status_code == 200:
                self.finished.emit(res.json()['result']['hosts'])
        except Exception as e:
            logger.error(str(e), exc_info=True)
            self.finished.emit([])

class SudoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setFixedWidth(300)
        
        layout = QVBoxLayout()
        
        # Message
        msg = QLabel("TuxCut Qt needs administrator privileges.\nPlease enter your password:")
        layout.addWidget(msg)
        
        # Password field
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)
        
        # Buttons
        button_box = QVBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_box.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addWidget(self.cancel_button)
        
        layout.addLayout(button_box)
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(800, 600)
        
        # Check if running with sudo and handle authentication
        if not self.ensure_root_access():
            sys.exit(1)
        
        # Start server
        self.server_thread = ServerThread()
        self.start_server()
        
        # Initialize variables
        self.aliases_file = os.path.join(APP_DIR, 'aliases.json')
        self.load_aliases()
        self._gw = dict()
        self._my = dict()
        self.live_hosts = list()
        self._offline_hosts = list()
        
        # Setup UI
        self.setup_menu()
        self.setup_ui()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Wait for server to start
        self.wait_for_server()
        
        # Check server and initialize
        if not self.is_server():
            self.show_error('TuxCut Qt Server Error',
                          'Could not start TuxCut Qt server. Check the logs for details.')
            self.close()
            return
            
        # Get gateway info
        self.get_gw()
        if not self._gw:
            self.show_error('Network Error', 
                          'Could not get gateway information. Please check your network connection.')
            self.close()
            return
            
        try:
            iface = self._gw.get('iface')
            if not iface:
                self.show_error('Network Error',
                              'Could not determine network interface')
                self.close()
                return
                
            self.get_my(iface)
            if not self._my:
                self.show_error('Network Error',
                              'Could not get local network information')
                self.close()
                return
                
            self.refresh_hosts()
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            self.show_error('Error',
                          'Failed to initialize application. Check the logs for details.')
            self.close()
    
    def setup_menu(self):
        pass  # Hapus menu karena About sudah dipindah ke toolbar
    
    def show_about(self):
        QMessageBox.about(self, f'About {APP_NAME}', ABOUT_TEXT)
    
    def start_server(self):
        self.server_thread = ServerThread()
        self.server_thread.start()
    
    def wait_for_server(self):
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            try:
                requests.get('http://127.0.0.1:8013/status')
                return
            except:
                attempt += 1
                time.sleep(1)
        
        self.show_error('Server Error', 'Could not connect to TuxCut server')
        self.close()
    
    def load_aliases(self):
        try:
            with open(self.aliases_file, 'r') as f:
                self.aliases = json.load(f)
        except FileNotFoundError:
            self.aliases = {}
            self.save_aliases()
    
    def save_aliases(self):
        with open(self.aliases_file, 'w') as f:
            json.dump(self.aliases, f)
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Top panel with protection combo
        top_panel = QHBoxLayout()
        protect_label = QLabel("Protection Mode:")
        self.protect_combo = QComboBox()
        self.protect_combo.addItems(["Disabled", "Enabled"])
        self.protect_combo.currentTextChanged.connect(self.on_protection_changed)
        top_panel.addWidget(protect_label)
        top_panel.addWidget(self.protect_combo)
        top_panel.addStretch()
        layout.addLayout(top_panel)
        
        # Hosts view
        self.hosts_view = QTreeWidget()
        self.hosts_view.setHeaderLabels(['Status', 'IP Address', 'MAC Address', 'Hostname', 'Alias'])
        self.hosts_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.hosts_view)
    
    def setup_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Add actions
        refresh_action = QAction("Refresh", self)
        refresh_action.setStatusTip("Refresh hosts list")
        refresh_action.triggered.connect(self.refresh_hosts)
        toolbar.addAction(refresh_action)
        
        cut_action = QAction("Cut", self)
        cut_action.setStatusTip("Cut selected host")
        cut_action.triggered.connect(self.cut_host)
        toolbar.addAction(cut_action)
        
        resume_action = QAction("Resume", self)
        resume_action.setStatusTip("Resume selected host")
        resume_action.triggered.connect(self.resume_host)
        toolbar.addAction(resume_action)
        
        toolbar.addSeparator()
        
        mac_action = QAction("Change MAC", self)
        mac_action.setStatusTip("Change MAC Address")
        mac_action.triggered.connect(self.change_mac)
        toolbar.addAction(mac_action)
        
        alias_action = QAction("Alias", self)
        alias_action.setStatusTip("Give an alias")
        alias_action.triggered.connect(self.give_alias)
        toolbar.addAction(alias_action)
        
        toolbar.addSeparator()
        
        about_action = QAction("About", self)
        about_action.setStatusTip("About TuxCut Qt")
        about_action.triggered.connect(self.show_about)
        toolbar.addAction(about_action)
        
        exit_action = QAction("Exit", self)
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        toolbar.addAction(exit_action)
    
    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")
    
    def refresh_hosts(self):
        self.statusbar.showMessage("Refreshing hosts list...")
        self.scan_thread = ScanThread(self._my['ip'])
        self.scan_thread.finished.connect(self.update_hosts_view)
        self.scan_thread.start()
    
    def update_hosts_view(self, hosts):
        self.hosts_view.clear()
        self.live_hosts = hosts
        
        for host in hosts:
            item = QTreeWidgetItem()
            status = "Offline" if host['ip'] in self._offline_hosts else "Online"
            item.setText(0, status)
            item.setText(1, host['ip'])
            item.setText(2, host['mac'])
            item.setText(3, host['hostname'])
            try:
                alias = self.aliases.get(host['mac'], '')
                item.setText(4, alias)
            except:
                item.setText(4, '')
            
            self.hosts_view.addTopLevelItem(item)
        
        self.statusbar.showMessage("Ready")
    
    def cut_host(self):
        current_item = self.hosts_view.currentItem()
        if current_item:
            victim = {
                'ip': current_item.text(1),
                'mac': current_item.text(2),
                'hostname': current_item.text(3)
            }
            
            res = requests.post('http://127.0.0.1:8013/cut', json=victim)
            if res.status_code == 200 and res.json()['status'] == 'success':
                if victim['ip'] not in self._offline_hosts:
                    self._offline_hosts.append(victim['ip'])
                self.statusbar.showMessage(f"{victim['ip']} is now offline")
                self.refresh_hosts()
        else:
            self.statusbar.showMessage("Please select a host to cut")
    
    def resume_host(self):
        current_item = self.hosts_view.currentItem()
        if current_item:
            victim = {
                'ip': current_item.text(1),
                'mac': current_item.text(2),
                'hostname': current_item.text(3)
            }
            
            res = requests.post('http://127.0.0.1:8013/resume', json=victim)
            if res.status_code == 200 and res.json()['status'] == 'success':
                if victim['ip'] in self._offline_hosts:
                    self._offline_hosts.remove(victim['ip'])
                self.statusbar.showMessage(f"{victim['ip']} is back online")
                self.refresh_hosts()
    
    def change_mac(self):
        res = requests.get(f'http://127.0.0.1:8013/change-mac/{self._gw["iface"]}')
        if res.status_code == 200:
            if res.json()['result']['status'] == 'success':
                self.statusbar.showMessage('MAC Address changed')
            else:
                self.statusbar.showMessage("Couldn't change MAC")
    
    def give_alias(self):
        current_item = self.hosts_view.currentItem()
        if not current_item:
            self.show_error('No Computer selected', 'Please select a computer from the list')
            return
            
        mac = current_item.text(2)
        alias, ok = QInputDialog.getText(
            self,
            'Enter Alias',
            f'Enter an alias for the computer with MAC "{mac}":',
            text='My Computer'
        )
        
        if ok and alias:
            self.aliases[mac] = alias
            self.save_aliases()
            self.refresh_hosts()
    
    def is_server(self):
        try:
            res = requests.get('http://127.0.0.1:8013/status')
            return res.status_code == 200 and res.json()['status'] == 'success'
        except:
            logger.error(sys.exc_info()[1], exc_info=True)
            return False
    
    def get_gw(self):
        try:
            res = requests.get('http://127.0.0.1:8013/gw')
            if res.status_code == 200 and res.json()['status'] == 'success':
                self._gw = res.json()['gw']
            elif res.status_code == 200 and res.json()['status'] == 'error':
                self.show_error('Error', res.json()['msg'])
                self.close()
                sys.exit()
        except Exception as e:
            logger.error(sys.exc_info()[1], exc_info=True)
    
    def get_my(self, iface):
        try:
            res = requests.get(f'http://127.0.0.1:8013/my/{iface}')
            if res.status_code == 200 and res.json()['status'] == 'success':
                self._my = res.json()['my']
            elif res.status_code == 200 and res.json()['status'] == 'error':
                self.show_error('Error', res.json()['msg'])
                self.close()
        except Exception as e:
            logger.error(sys.exc_info()[1], exc_info=True)
    
    def show_error(self, title, message):
        QMessageBox.critical(self, title, message)
    
    def closeEvent(self, event):
        try:
            # Nonaktifkan protection jika aktif
            if self.protect_combo.currentText() == "Enabled":
                try:
                    requests.post('http://127.0.0.1:8013/unprotect')
                except:
                    pass
            
            # Simpan aliases
            self.save_aliases()
            
            # Hentikan server
            if hasattr(self, 'server_thread'):
                self.server_thread.stop()
            
            # Pastikan aplikasi benar-benar tertutup
            self.deleteLater()
            QApplication.quit()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
        
        event.accept()
    
    def ensure_root_access(self):
        if os.geteuid() == 0:
            return True
            
        dialog = SudoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.password.text()
            try:
                # Rerun dengan sudo dan preserve environment untuk DISPLAY
                current_script = os.path.abspath(sys.argv[0])
                python_path = os.path.join(os.path.dirname(os.path.dirname(current_script)), '.venv', 'bin', 'python')
                
                env = os.environ.copy()
                
                cmd = ['sudo', '-E', python_path, current_script]
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    env=env
                )
                
                stdout, stderr = process.communicate(input=password + '\n')
                
                if process.returncode == 0:
                    sys.exit(0)  # Exit karena aplikasi baru sudah berjalan
                else:
                    self.show_error("Authentication Failed", "Incorrect password")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to gain root access: {str(e)}")
                self.show_error("Error", f"Failed to gain root access: {str(e)}")
                return False
        return False 
    
    def on_protection_changed(self, text):
        try:
            if text == "Enabled":
                res = requests.post('http://127.0.0.1:8013/protect', json=self._gw)
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.statusbar.showMessage('Protection Enabled')
                else:
                    self.protect_combo.setCurrentText("Disabled")
                    self.statusbar.showMessage("Couldn't enable protection")
            else:
                res = requests.post('http://127.0.0.1:8013/unprotect')
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.statusbar.showMessage('Protection Disabled')
                else:
                    self.protect_combo.setCurrentText("Enabled")
                    self.statusbar.showMessage("Couldn't disable protection")
        except Exception as e:
            logger.error(f"Protection toggle error: {str(e)}")
            self.statusbar.showMessage("Error toggling protection") 