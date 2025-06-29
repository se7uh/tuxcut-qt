# Standard library imports
import os # For interacting with the operating system (e.g., file paths, environment variables)
import sys # For system-specific parameters and functions (e.g., exit)
import json # For working with JSON data (e.g., loading/saving aliases)
import logging # For logging application events and errors
from pathlib import Path # For object-oriented filesystem paths
import requests # For making HTTP requests to the TuxCut Qt server
from threading import Thread # For running background tasks (e.g., server status checks)

# PySide6 (Qt for Python) imports for GUI components
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QToolBar, QStatusBar, QMessageBox,
    QInputDialog, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenuBar, QMenu,
    QDialog, QLabel, QLineEdit, QPushButton, QHBoxLayout, QSplitter,
    QTextEdit, QComboBox, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal # Core Qt functionalities, threading, and signals
from PySide6.QtGui import QAction, QIcon, QPixmap # GUI elements like actions, icons, and pixel maps

# Local application configuration imports
from config import APP_NAME, ABOUT_TEXT # Application name and about text from config.py

# --- Application Directory and Logging Setup ---

# Define the application directory in the user's home folder
APP_DIR = os.path.join(str(Path.home()), '.tuxcut')

# Create the application directory if it doesn't exist
if not os.path.isdir(APP_DIR):
    os.mkdir(APP_DIR)
    # Create and set permissions for the client log file
    client_log = Path(os.path.join(APP_DIR, 'tuxcut.log'))
    client_log.touch(exist_ok=True)
    client_log.chmod(0o666)

# Configure basic logging for the application
logging.basicConfig(level=logging.INFO) # Set default logging level to INFO
logger = logging.getLogger('tuxcut-client') # Get a logger instance for the client
handler = logging.FileHandler(os.path.join(APP_DIR, 'tuxcut.log')) # File handler for logging to a file
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Log message format
handler.setFormatter(formatter) # Apply the formatter to the handler
logger.addHandler(handler) # Add the file handler to the logger


# --- Thread for Background Scanning ---

class ScanThread(QThread):
    """
    A QThread subclass for performing network scans in a separate thread
    to keep the GUI responsive.
    Emits a signal with the list of scanned hosts when finished.
    """
    finished = pyqtSignal(list) # Signal emitted when scanning is complete, carrying a list of hosts
    
    def __init__(self, ip):
        """
        Initializes the ScanThread.
        :param ip: The IP address to scan.
        """
        super().__init__()
        self.ip = ip
        
    def run(self):
        """
        The main execution method of the thread.
        Performs an HTTP GET request to the local server to initiate a scan.
        Emits the results or an empty list if an error occurs.
        """
        try:
            res = requests.get(f'http://127.0.0.1:8013/scan/{self.ip}')
            if res.status_code == 200:
                self.finished.emit(res.json()['result']['hosts'])
        except Exception as e:
            logger.error(f"Error during scan thread execution: {str(e)}", exc_info=True)
            self.finished.emit([]) # Emit empty list on error

# --- Sudo Authentication Dialog ---

class SudoDialog(QDialog):
    """
    A custom QDialog for requesting administrator (sudo) password from the user.
    This is used when the application needs elevated privileges.
    """
    def __init__(self, parent=None):
        """
        Initializes the SudoDialog.
        :param parent: The parent widget of this dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setFixedWidth(300) # Set a fixed width for the dialog
        
        layout = QVBoxLayout() # Main vertical layout for the dialog content
        
        # Message label instructing the user to enter their password
        msg = QLabel("TuxCut Qt requires administrator privileges to function.\nPlease enter your password to continue:")
        layout.addWidget(msg)
        
        # Password input field, with echo mode set to hide characters
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)
        
        # Layout for OK and Cancel buttons
        button_box = QVBoxLayout()
        
        # OK button to accept the password
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept) # Connects to QDialog's accept slot
        button_box.addWidget(self.ok_button)
        
        # Cancel button to reject the dialog
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject) # Connects to QDialog's reject slot
        button_box.addWidget(self.cancel_button)
        
        layout.addLayout(button_box) # Add the button layout to the main dialog layout
        self.setLayout(layout) # Set the main layout for the dialog

class MainWindow(QMainWindow):
    """
    The main application window for TuxCut Qt.
    Manages the UI, interactions with the backend server, and host management.
    """
    def __init__(self):
        """
        Initializes the main window, sets up the UI, and performs initial checks.
        """
        super().__init__()
        self.setWindowTitle(APP_NAME) # Set window title from config
        self.setMinimumSize(800, 600) # Set minimum window size for responsiveness
        
        # Ensure the application is running with root privileges
        if not self.ensure_root_access():
            sys.exit(1) # Exit if root access is not granted
        
        # --- Initialize Member Variables ---
        # Path to the aliases JSON file
        self.aliases_file = os.path.join(APP_DIR, 'aliases.json')
        self.load_aliases() # Load existing aliases
        self._gw = dict() # Stores gateway information
        self._my = dict() # Stores local network information
        self.live_hosts = list() # List of currently online hosts
        self._offline_hosts = list() # List of hosts marked as offline (cut)
        
        # --- Setup User Interface Components ---
        self.setup_menu() # Setup application menus (currently empty as actions are in toolbar)
        self.setup_ui() # Setup the main central widget and layouts
        self.setup_toolbar() # Setup the application toolbar with actions
        self.setup_statusbar() # Setup the status bar at the bottom of the window
        
        # --- Initial Server and Network Checks ---
        # Check if the TuxCut Qt server is running and accessible
        if not self.is_server():
            self.show_error('Server Connection Error',
                          'Failed to connect to the TuxCut Qt server. Please ensure the server is running and accessible.')
            self.close() # Close application if server is not reachable
            return
            
        # Get gateway information from the server
        self.get_gw()
        if not self._gw:
            self.show_error('Network Configuration Error',
                          'Unable to retrieve gateway information. Please verify your network connection and settings.')
            self.close() # Close if gateway info cannot be obtained
            return
            
        try:
            # Determine the network interface
            iface = self._gw.get('iface')
            if not iface:
                self.show_error('Network Interface Error',
                              'Failed to determine the active network interface. Please check your network configuration.')
                self.close() # Close if interface cannot be determined
                return
                
            # Get local network information using the determined interface
            self.get_my(iface)
            if not self._my:
                self.show_error('Local Network Information Error',
                              'Unable to retrieve local network details. Please ensure your network is properly configured.')
                self.close() # Close if local network info cannot be obtained
                return
                
            self.refresh_hosts() # Refresh the hosts list on successful initialization
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}", exc_info=True)
            self.show_error('Application Initialization Failed',
                          'The application failed to initialize. Please check the application logs for more detailed error information.')
            self.close() # Close on any unhandled initialization error
    
    def setup_menu(self):
        # Menus are not currently used, actions are in toolbar
        pass
    
    def show_about(self):
        QMessageBox.about(self, f'About {APP_NAME}', ABOUT_TEXT)
    
    
    
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
        main_layout = QVBoxLayout(central_widget)
        
        # Top panel for protection mode
        protection_panel = QWidget()
        protection_layout = QHBoxLayout(protection_panel)
        protect_label = QLabel("Protection Mode:")
        self.protect_combo = QComboBox()
        self.protect_combo.addItems(["Disabled", "Enabled"])
        self.protect_combo.currentTextChanged.connect(self.on_protection_changed)
        protection_layout.addWidget(protect_label)
        protection_layout.addWidget(self.protect_combo)
        protection_layout.addStretch()
        protection_panel.setLayout(protection_layout)
        protection_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed) # Ensure panel doesn't stretch vertically

        # Hosts view
        self.hosts_view = QTreeWidget()
        self.hosts_view.setHeaderLabels(['Status', 'IP Address', 'MAC Address', 'Hostname', 'Alias'])
        
        header = self.hosts_view.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed) # Status column
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # IP Address
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # MAC Address
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Hostname
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Alias
        
        self.hosts_view.setAlternatingRowColors(True) # Enable alternating row colors
        
        # Use QSplitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(protection_panel)
        splitter.addWidget(self.hosts_view)
        
        # Set initial sizes (optional, but good for default appearance)
        splitter.setSizes([self.height() * 0.1, self.height() * 0.9]) # 10% for top, 90% for hosts

        main_layout.addWidget(splitter)
    
    def setup_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Define icon paths
        icon_path = lambda icon_name: os.path.join(os.path.dirname(__file__), 'images', icon_name)

        # Add actions
        refresh_action = QAction(QIcon(icon_path('refresh_32.png')), "Refresh", self)
        refresh_action.setStatusTip("Refresh hosts list")
        refresh_action.triggered.connect(self.refresh_hosts)
        toolbar.addAction(refresh_action)
        
        cut_action = QAction(QIcon(icon_path('cut_32.png')), "Cut", self)
        cut_action.setStatusTip("Cut selected host")
        cut_action.triggered.connect(self.cut_host)
        toolbar.addAction(cut_action)
        
        resume_action = QAction(QIcon(icon_path('resume_32.png')), "Resume", self)
        resume_action.setStatusTip("Resume selected host")
        resume_action.triggered.connect(self.resume_host)
        toolbar.addAction(resume_action)
        
        toolbar.addSeparator()
        
        mac_action = QAction(QIcon(icon_path('mac_32.png')), "Change MAC", self)
        mac_action.setStatusTip("Change MAC Address")
        mac_action.triggered.connect(self.change_mac)
        toolbar.addAction(mac_action)
        
        alias_action = QAction(QIcon(icon_path('alias_32.png')), "Alias", self)
        alias_action.setStatusTip("Give an alias")
        alias_action.triggered.connect(self.give_alias)
        toolbar.addAction(alias_action)
        
        toolbar.addSeparator()
        
        about_action = QAction(QIcon(icon_path('ninja_32.png')), "About", self)
        about_action.setStatusTip("About TuxCut Qt")
        about_action.triggered.connect(self.show_about)
        toolbar.addAction(about_action)
        
        exit_action = QAction(QIcon(icon_path('exit_32.png')), "Exit", self)
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        toolbar.addAction(exit_action)

        # Update hosts view status icons
        self.online_icon = QIcon(icon_path('online_24.png'))
        self.offline_icon = QIcon(icon_path('offline_24.png'))
    
    def setup_statusbar(self):
        """
        Sets up the application's status bar at the bottom of the main window.
        Used to display brief messages to the user about application status.
        """
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar) # Set the status bar for the main window
        self.statusbar.showMessage("Application Ready") # Initial status message
    
    def refresh_hosts(self):
        """
        Initiates a scan for network hosts in a separate thread and updates the UI
        when the scan is complete. Displays status messages in the status bar.
        """
        self.statusbar.showMessage("Refreshing host list, please wait...")
        self.scan_thread = ScanThread(self._my['ip']) # Create a new scan thread
        self.scan_thread.finished.connect(self.update_hosts_view) # Connect thread's finished signal to update method
        self.scan_thread.start() # Start the scan thread
    
    def update_hosts_view(self, hosts):
        """
        Updates the QTreeWidget (hosts_view) with the latest list of hosts.
        Sets appropriate icons (online/offline) and displays aliases.
        :param hosts: A list of host dictionaries (e.g., [{'ip': '...', 'mac': '...', 'hostname': '...'}])
        """
        self.hosts_view.clear() # Clear existing items in the tree view
        self.live_hosts = hosts # Store the live hosts list
        
        for host in hosts:
            item = QTreeWidgetItem() # Create a new tree widget item for each host
            # Set icon based on whether the host is marked as offline
            if host['ip'] in self._offline_hosts:
                item.setIcon(0, self.offline_icon)
            else:
                item.setIcon(0, self.online_icon)
            
            # Set text for each column
            item.setText(1, host['ip'])
            item.setText(2, host['mac'])
            item.setText(3, host['hostname'])
            try:
                # Retrieve and set alias, if available
                alias = self.aliases.get(host['mac'], '')
                item.setText(4, alias)
            except:
                item.setText(4, '') # Set empty string if alias retrieval fails
            
            self.hosts_view.addTopLevelItem(item) # Add the item to the tree view
        
        self.statusbar.showMessage("Host list updated.") # Update status bar
    
    def cut_host(self):
        """
        Disconnects the selected host from the network by sending a 'cut' request to the server.
        Updates the status bar and refreshes the host list.
        """
        current_item = self.hosts_view.currentItem() # Get the currently selected item
        if current_item:
            # Extract victim information from the selected item
            victim = {
                'ip': current_item.text(1),
                'mac': current_item.text(2),
                'hostname': current_item.text(3)
            }
            
            res = requests.post('http://127.0.0.1:8013/cut', json=victim) # Send cut request
            if res.status_code == 200 and res.json()['status'] == 'success':
                # Add to offline list if successful and not already there
                if victim['ip'] not in self._offline_hosts:
                    self._offline_hosts.append(victim['ip'])
                self.statusbar.showMessage(f"Host {victim['ip']} is now offline.") # Update status bar
                self.refresh_hosts() # Refresh host list to show updated status
        else:
            self.statusbar.showMessage("Please select a host to disconnect.") # Prompt user to select a host
    
    def resume_host(self):
        """
        Reconnects the selected host to the network by sending a 'resume' request to the server.
        Updates the status bar and refreshes the host list.
        """
        current_item = self.hosts_view.currentItem() # Get the currently selected item
        if current_item:
            # Extract victim information from the selected item
            victim = {
                'ip': current_item.text(1),
                'mac': current_item.text(2),
                'hostname': current_item.text(3)
            }
            
            res = requests.post('http://127.0.0.1:8013/resume', json=victim) # Send resume request
            if res.status_code == 200 and res.json()['status'] == 'success':
                # Remove from offline list if successful
                if victim['ip'] in self._offline_hosts:
                    self._offline_hosts.remove(victim['ip'])
                self.statusbar.showMessage(f"Host {victim['ip']} is back online.") # Update status bar
                self.refresh_hosts() # Refresh host list to show updated status
    
    def change_mac(self):
        """
        Changes the MAC address of the network interface by sending a request to the server.
        Updates the status bar with the result.
        """
        res = requests.get(f'http://127.0.0.1:8013/change-mac/{self._gw["iface"]}') # Send change MAC request
        if res.status_code == 200:
            if res.json()['result']['status'] == 'success':
                self.statusbar.showMessage('MAC Address successfully changed.') # Success message
            else:
                self.statusbar.showMessage("Failed to change MAC Address.") # Failure message
    
    def give_alias(self):
        """
        Prompts the user to enter an alias for the selected host and saves it.
        Updates the status bar and refreshes the host list.
        """
        current_item = self.hosts_view.currentItem() # Get the currently selected item
        if not current_item:
            self.show_error('No Host Selected', 'Please select a host from the list to assign an alias.')
            return # Exit if no host is selected
            
        mac = current_item.text(2) # Get MAC address of the selected host
        # Open an input dialog to get the alias from the user
        alias, ok = QInputDialog.getText(
            self,
            'Enter Alias',
            f'Enter a descriptive alias for the host with MAC address "{mac}":',
            text='My Device' # Default text for the input field
        )
        
        if ok and alias: # If user clicked OK and entered an alias
            self.aliases[mac] = alias # Store the alias
            self.save_aliases() # Save aliases to file
            self.refresh_hosts() # Refresh host list to display new alias
    
    def is_server(self):
        """
        Checks if the TuxCut Qt server is running and accessible.
        :return: True if the server is running and returns success status, False otherwise.
        """
        try:
            res = requests.get('http://127.0.0.1:8013/status') # Send status request to server
            return res.status_code == 200 and res.json()['status'] == 'success'
        except Exception as e:
            logger.error(f"Server status check failed: {sys.exc_info()[1]}", exc_info=True)
            return False
    
    def get_gw(self):
        """
        Retrieves gateway information from the TuxCut Qt server.
        Displays an error and closes the application if retrieval fails.
        """
        try:
            res = requests.get('http://127.0.0.1:8013/gw') # Request gateway info
            if res.status_code == 200 and res.json()['status'] == 'success':
                self._gw = res.json()['gw'] # Store gateway info
            elif res.status_code == 200 and res.json()['status'] == 'error':
                # Display server-side error message
                self.show_error('Error', res.json()['msg'])
                self.close()
                sys.exit() # Exit application on critical error
        except Exception as e:
            logger.error(f"Failed to get gateway information: {sys.exc_info()[1]}", exc_info=True)
    
    def get_my(self, iface):
        """
        Retrieves local network information (IP, MAC, etc.) for a given interface from the server.
        Displays an error and closes the application if retrieval fails.
        :param iface: The network interface name.
        """
        try:
            res = requests.get(f'http://127.0.0.1:8013/my/{iface}') # Request local network info
            if res.status_code == 200 and res.json()['status'] == 'success':
                self._my = res.json()['my'] # Store local network info
            elif res.status_code == 200 and res.json()['status'] == 'error':
                # Display server-side error message
                self.show_error('Error', res.json()['msg'])
                self.close()
        except Exception as e:
            logger.error(f"Failed to get local network information: {sys.exc_info()[1]}", exc_info=True)
    
    def show_error(self, title, message):
        """
        Displays a critical error message box to the user.
        :param title: The title of the error dialog.
        :param message: The error message to display.
        """
        QMessageBox.critical(self, title, message)
    
    def closeEvent(self, event):
        """
        Handles the application close event.
        Ensures protection mode is disabled and aliases are saved before closing.
        """
        try:
            # Attempt to disable protection mode if it's currently enabled
            if self.protect_combo.currentText() == "Enabled":
                try:
                    requests.post('http://127.0.0.1:8013/unprotect')
                except Exception as e:
                    logger.warning(f"Failed to disable protection during shutdown: {e}")
            
            # Save any updated aliases
            self.save_aliases()
            
            # Ensure the application truly quits
            self.deleteLater() # Deletes the widget when control returns to the event loop
            QApplication.quit() # Ensures all Qt event loops are terminated
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        
        event.accept() # Accept the close event
    
    def ensure_root_access(self):
        """
        Checks if the application is running with root (administrator) privileges.
        Displays an error message if not and prevents further execution.
        :return: True if running as root, False otherwise.
        """
        # With the new execution method, root access is handled by the calling script (sudo python ...)
        # This function is no longer needed for re-running the application with sudo.
        # We only need to check if the current process has root privileges.
        if os.geteuid() == 0: # Check if effective user ID is 0 (root)
            return True
        else:
            self.show_error("Permission Denied", "TuxCut Qt requires root privileges to run. Please run the application with 'sudo'.")
            return False
    
    def on_protection_changed(self, text):
        """
        Handles changes in the protection mode combobox.
        Sends requests to the server to enable or disable protection.
        Updates the status bar with the operation's result.
        :param text: The new text of the combobox (e.g., "Enabled" or "Disabled").
        """
        try:
            if text == "Enabled":
                # Send request to enable protection
                res = requests.post('http://127.0.0.1:8013/protect', json=self._gw)
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.statusbar.showMessage('Protection mode is now Enabled.')
                else:
                    self.protect_combo.setCurrentText("Disabled") # Revert combobox if failed
                    self.statusbar.showMessage("Failed to enable protection mode.")
            else:
                # Send request to disable protection
                res = requests.post('http://127.0.0.1:8013/unprotect')
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.statusbar.showMessage('Protection mode is now Disabled.')
                else:
                    self.protect_combo.setCurrentText("Enabled") # Revert combobox if failed
                    self.statusbar.showMessage("Failed to disable protection mode.")
        except Exception as e:
            logger.error(f"Protection toggle error: {str(e)}", exc_info=True)
            self.statusbar.showMessage("An error occurred while toggling protection.")