import sys
import os
import asyncio
import json
import logging
from datetime import datetime
import socket
import uuid
import traceback
import ctypes
import threading

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, 
    QMenu, QPushButton, QLineEdit, QMessageBox, QDialog, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter
import qasync
import aiohttp
import win32con
import win32api
import win32gui

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TimerOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('🎮 NetCafe Pro 2.0 - Session Timer')
        
        layout = QVBoxLayout(self)
        
        # Time display
        self.time_label = QLabel('00:00', self)
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet('''
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(0,0,0,0.9), stop:1 rgba(26,26,46,0.9));
            color: #00FF88; 
            font-size: 60px; 
            border-radius: 24px; 
            padding: 40px 20px; 
            font-weight: bold;
            border: 3px solid rgba(0,255,136,0.5);
        ''')
        layout.addWidget(self.time_label)
        
        # Status display
        self.status_label = QLabel('🟢 Session Active', self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('''
            color: white; 
            font-size: 18px; 
            margin-top: 8px; 
            background: rgba(0,255,136,0.2); 
            padding: 10px; 
            border-radius: 8px;
            border: 2px solid rgba(0,255,136,0.3);
        ''')
        layout.addWidget(self.status_label)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.minimize_btn = QPushButton('🔽 Minimize', self)
        self.minimize_btn.setStyleSheet(self.get_button_style('#00FF88'))
        
        self.end_btn = QPushButton('🛑 End Session', self)
        self.end_btn.setStyleSheet(self.get_button_style('#FF4444'))
        
        btn_layout.addWidget(self.minimize_btn)
        btn_layout.addWidget(self.end_btn)
        layout.addLayout(btn_layout)
        
        self.resize(800, 200)
        self.move(200, 40)
    
    def get_button_style(self, color):
        return f'''
            QPushButton {{
                font-size: 16px; 
                padding: 10px 20px; 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color}, stop:1 {color}AA);
                color: white; 
                border-radius: 8px; 
                font-weight: bold;
                border: 2px solid {color};
            }}
            QPushButton:hover {{
                background: {color};
                transform: translateY(-2px);
            }}
        '''
    
    def set_time(self, time_str):
        self.time_label.setText(time_str)
    
    def set_status(self, status):
        self.status_label.setText(status)

class LockScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet('''
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #0a0a0a, stop:1 #1a1a2e);
        ''')
        
        layout = QVBoxLayout(self)
        
        # Logo
        logo_label = QLabel('🎮 NetCafe Pro 2.0', self)
        logo_label.setStyleSheet('''
            color: #00FF88; 
            font-size: 56px; 
            font-weight: bold; 
            margin-bottom: 30px;
            background: rgba(0,255,136,0.1);
            padding: 20px;
            border-radius: 16px;
            border: 3px solid rgba(0,255,136,0.3);
        ''')
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        
        # Status message
        self.status_label = QLabel('🔒 Computer Locked', self)
        self.status_label.setStyleSheet('''
            color: white; 
            font-size: 36px; 
            font-weight: bold;
            margin-bottom: 20px;
        ''')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Details
        self.details_label = QLabel('Please login to start your session...', self)
        self.details_label.setStyleSheet('''
            color: #aaa; 
            font-size: 22px; 
            margin-top: 24px;
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 12px;
        ''')
        self.details_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.details_label)
        
        # Connection indicator
        self.connection_label = QLabel('🔴 Connecting to server...', self)
        self.connection_label.setStyleSheet('''
            color: #FF4444;
            font-size: 18px;
            margin-top: 20px;
            padding: 10px;
            background: rgba(255,68,68,0.2);
            border-radius: 8px;
            border: 2px solid rgba(255,68,68,0.3);
        ''')
        self.connection_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.connection_label)
    
    def show_lock(self, message='🔒 Computer Locked', details='Please login to continue...'):
        self.status_label.setText(message)
        self.details_label.setText(details)
        self.showFullScreen()
        self.raise_()
    
    def hide_lock(self):
        self.hide()
    
    def set_connection_status(self, status, connected=False):
        if connected:
            self.connection_label.setText(f'🟢 {status}')
            self.connection_label.setStyleSheet('''
                color: #00FF88;
                font-size: 18px;
                margin-top: 20px;
                padding: 10px;
                background: rgba(0,255,136,0.2);
                border-radius: 8px;
                border: 2px solid rgba(0,255,136,0.3);
            ''')
        else:
            self.connection_label.setText(f'🔴 {status}')
            self.connection_label.setStyleSheet('''
                color: #FF4444;
                font-size: 18px;
                margin-top: 20px;
                padding: 10px;
                background: rgba(255,68,68,0.2);
                border-radius: 8px;
                border: 2px solid rgba(255,68,68,0.3);
            ''')

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('🎮 NetCafe Pro 2.0 - Login')
        self.setFixedSize(450, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Dialog)
        
        # Gaming style
        self.setStyleSheet('''
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 12px;
                border: 3px solid rgba(0,255,136,0.5);
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
            QLineEdit {
                background: rgba(255,255,255,0.1);
                border: 2px solid rgba(0,255,136,0.3);
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #00FF88;
                background: rgba(255,255,255,0.15);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00FF88, stop:1 #00D4AA);
                color: black;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00D4AA, stop:1 #00FF88);
                transform: translateY(-2px);
            }
        ''')
        
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel('🎮 Welcome to NetCafe Pro 2.0')
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet('''
            font-size: 20px; 
            font-weight: bold; 
            color: #00FF88; 
            margin-bottom: 20px;
            background: rgba(0,255,136,0.1);
            padding: 15px;
            border-radius: 8px;
        ''')
        layout.addWidget(header_label)
        
        # Username
        layout.addWidget(QLabel('👤 Username:'))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Enter your username')
        layout.addWidget(self.username_input)
        
        # Password
        layout.addWidget(QLabel('🔒 Password:'))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Enter your password')
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton('❌ Cancel')
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet('''
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FF4444, stop:1 #CC3333);
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FF6666, stop:1 #FF4444);
            }
        ''')
        
        login_btn = QPushButton('🚀 Start Gaming')
        login_btn.clicked.connect(self.try_login)
        login_btn.setDefault(True)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(login_btn)
        layout.addLayout(btn_layout)
        
        # Connect Enter key
        self.password_input.returnPressed.connect(self.try_login)
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        
        self.accepted_login = False
    
    def try_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, '⚠️ Warning', 'Please enter both username and password!')
            return
        self.accepted_login = True
        self.accept()
    
    def get_credentials(self):
        return self.username_input.text().strip(), self.password_input.text().strip()

class KeyboardBlocker:
    def __init__(self):
        self.hooked = None
        self.enabled = False
    
    def install(self):
        if self.hooked or not ctypes.windll.kernel32.GetModuleHandleW:
            return
        
        try:
            CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
            
            def low_level_keyboard_proc(nCode, wParam, lParam):
                if nCode == 0:
                    vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong * 6))[0][0]
                    # Block Windows keys and Ctrl+Esc
                    if vk_code in (0x5B, 0x5C) or (vk_code == 0x1B and (win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000)):
                        return 1
                return ctypes.windll.user32.CallNextHookEx(self.hooked, nCode, wParam, lParam)
            
            self.pointer = CMPFUNC(low_level_keyboard_proc)
            self.hooked = ctypes.windll.user32.SetWindowsHookExA(13, self.pointer, ctypes.windll.kernel32.GetModuleHandleW(None), 0)
            self.enabled = True
            
            def msg_loop():
                while self.enabled:
                    ctypes.windll.user32.PeekMessageW(None, 0, 0, 0, 0)
            
            self.thread = threading.Thread(target=msg_loop, daemon=True)
            self.thread.start()
            logger.info("Keyboard blocker installed")
        except Exception as e:
            logger.error(f"Failed to install keyboard blocker: {e}")
    
    def uninstall(self):
        if self.hooked:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self.hooked)
                self.hooked = None
                self.enabled = False
                logger.info("Keyboard blocker uninstalled")
            except Exception as e:
                logger.error(f"Failed to uninstall keyboard blocker: {e}")

class NetCafeClient:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.loop = qasync.QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)
        
        # Load configuration
        self.config = self._load_config()
        
        # Components
        self.timer_overlay = TimerOverlay()
        self.lock_screen = LockScreen()
        self.keyboard_blocker = KeyboardBlocker()
        
        # State
        self.session_active = False
        self.remaining_time = 0
        self.session_id = None
        self.computer_id = self._get_computer_id()
        
        # Server configuration
        self.server_hosts = [self.config['server']['host']] + self.config['server'].get('fallback_hosts', [])
        self.server_port = self.config['server']['port']
        self.current_host_index = 0
        
        # Network
        self.session = None
        self.ws = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = self.config['server']['max_reconnect_attempts']
        
        # Timers
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self._tick)
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._try_reconnect)
        
        # Notifications
        self._notified_5min = False
        self._notified_1min = False
        
        # Initialize system tray and UI
        self._init_tray()
        
        # Connect overlay button signals
        self.timer_overlay.minimize_btn.clicked.connect(self._minimize_overlay)
        self.timer_overlay.end_btn.clicked.connect(lambda: asyncio.create_task(self._end_session()))
        
        # Start with lock screen
        self._show_lock_screen()
        
        logger.info(f"NetCafe Client initialized. Computer ID: {self.computer_id}")
        
        # Set initial status
        self.set_status('Initializing...', False)
    
    def _load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}, using defaults")
            return {
                "server": {
                    "host": "localhost",
                    "port": 8080,
                    "websocket_endpoint": "/ws",
                    "max_reconnect_attempts": 10,
                    "fallback_hosts": ["127.0.0.1"]
                }
            }
    
    def _get_current_server_url(self):
        """Get current server URL based on host index"""
        if self.current_host_index < len(self.server_hosts):
            host = self.server_hosts[self.current_host_index]
            return f"http://{host}:{self.server_port}"
        return f"http://{self.server_hosts[0]}:{self.server_port}"
    
    def _get_computer_id(self):
        try:
            hostname = socket.gethostname()
            mac = uuid.getnode()
            return f"{hostname}_{mac}"
        except Exception:
            return f"client_{uuid.uuid4().hex[:8]}"
    
    def _init_tray(self):
        try:
            self.tray = QSystemTrayIcon()
            
            # Create gaming icon
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setBrush(Qt.green)
            painter.drawEllipse(2, 2, 28, 28)
            painter.setBrush(Qt.black)
            painter.drawEllipse(8, 8, 16, 16)
            painter.end()
            
            self.tray.setIcon(QIcon(pixmap))
            self.tray.setToolTip('🎮 NetCafe Pro 2.0 - Gaming Client')
            
            # Context menu
            menu = QMenu()
            
            self.status_action = QAction('🔴 Disconnected')
            self.status_action.setEnabled(False)
            menu.addAction(self.status_action)
            
            menu.addSeparator()
            
            show_timer_action = QAction('⏰ Show Timer')
            show_timer_action.triggered.connect(self._show_overlay)
            menu.addAction(show_timer_action)
            
            reconnect_action = QAction('🔄 Reconnect')
            reconnect_action.triggered.connect(self._manual_reconnect)
            menu.addAction(reconnect_action)
            
            menu.addSeparator()
            
            exit_action = QAction('❌ Exit')
            exit_action.triggered.connect(self._exit)
            menu.addAction(exit_action)
            
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()
            
            logger.info("System tray initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tray: {e}")
    
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.session_active:
                self._show_overlay()
            else:
                self._show_lock_screen()
    
    def _show_lock_screen(self):
        self.lock_screen.show_lock()
        self.keyboard_blocker.install()
    
    def _hide_lock_screen(self):
        self.lock_screen.hide_lock()
        self.keyboard_blocker.uninstall()
    
    def _show_overlay(self):
        if self.session_active:
            self.timer_overlay.show()
            self.timer_overlay.raise_()
            self.timer_overlay.activateWindow()
    
    def _minimize_overlay(self):
        self.timer_overlay.hide()
        self.tray.showMessage(
            '🎮 NetCafe Pro 2.0',
            'Timer minimized. Double-click tray icon to restore.',
            QSystemTrayIcon.Information,
            3000
        )
    
    def _manual_reconnect(self):
        self.reconnect_attempts = 0
        asyncio.create_task(self.connect_to_server())
    
    def _exit(self):
        if self.session_active:
            asyncio.create_task(self._end_session())
        self._cleanup()
        self.app.quit()
    
    def _cleanup(self):
        try:
            self.session_timer.stop()
            self.reconnect_timer.stop()
            self.keyboard_blocker.uninstall()
            if self.session:
                asyncio.create_task(self.session.close())
            self.tray.hide()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    async def connect_to_server(self):
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.set_status('Max reconnect attempts reached', False)
            return
        
        try:
            server_url = self._get_current_server_url()
            logger.info(f"Connecting to server: {server_url}")
            self.set_status('Connecting to server...', False)
            
            if self.session:
                await self.session.close()
            
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            
            # Test connection
            async with self.session.get(f'{server_url}/api/status') as response:
                if response.status == 200:
                    logger.info("Server is reachable")
                else:
                    raise Exception(f"Server status: {response.status}")
            
            # Connect WebSocket
            host = self.server_hosts[self.current_host_index]
            ws_url = f"ws://{host}:{self.server_port}/ws?computer_id={self.computer_id}"
            self.ws = await self.session.ws_connect(ws_url)
            logger.info("WebSocket connected")
            
            asyncio.create_task(self._handle_ws_messages())
            
            self.set_status('Connected - Ready for gaming!', True)
            self.reconnect_attempts = 0
            
            # Show login
            await self.show_login()
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.reconnect_attempts += 1
            
            # Try next host if available
            if self.current_host_index < len(self.server_hosts) - 1:
                self.current_host_index += 1
                logger.info(f"Trying next host: {self.server_hosts[self.current_host_index]}")
            else:
                self.current_host_index = 0  # Reset to first host
            
            self.set_status(f'Connection failed (attempt {self.reconnect_attempts})', False)
            
            if self.session:
                await self.session.close()
                self.session = None
            
            self._start_reconnect_timer()
    
    async def show_login(self):
        try:
            dialog = LoginDialog()
            if dialog.exec() and dialog.accepted_login:
                username, password = dialog.get_credentials()
                await self.authenticate(username, password)
            else:
                logger.info("Login cancelled")
        except Exception as e:
            logger.error(f"Login dialog error: {e}")
    
    async def authenticate(self, username, password):
        try:
            login_data = {
                'username': username,
                'password': password,
                'computer_id': self.computer_id
            }
            
            logger.info(f"Authenticating user: {username}")
            
            server_url = self._get_current_server_url()
            async with self.session.post(f'{server_url}/api/login', json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        self.session_id = data.get('session_id')
                        minutes = data.get('minutes', 0)
                        
                        logger.info(f"Login successful: {username}, {minutes} minutes")
                        
                        if minutes > 0:
                            await self.start_session(minutes)
                        else:
                            QMessageBox.warning(None, '⚠️ No Time', 'No time available!')
                    else:
                        QMessageBox.critical(None, '❌ Login Failed', data.get('message', 'Login failed'))
                else:
                    QMessageBox.critical(None, '❌ Error', f'Server error: {response.status}')
                    
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            QMessageBox.critical(None, '❌ Error', f'Authentication failed: {str(e)}')
    
    async def start_session(self, minutes):
        try:
            logger.info(f"Starting session: {minutes} minutes")
            
            self.session_active = True
            self.remaining_time = minutes * 60
            self.session_timer.start(1000)
            self._notified_5min = False
            self._notified_1min = False
            
            self._hide_lock_screen()
            self._show_overlay()
            self._update_timer()
            
            self.set_status('🎮 Gaming Session Active', True)
            
            self.tray.showMessage(
                '🎮 NetCafe Pro 2.0',
                f'Gaming session started! {minutes} minutes available.',
                QSystemTrayIcon.Information,
                5000
            )
            
        except Exception as e:
            logger.error(f"Start session error: {e}")
    
    async def _end_session(self):
        try:
            logger.info("Ending session")
            
            if self.session_id:
                minutes_used = (self.remaining_time // 60) if self.remaining_time else 0
                logout_data = {
                    'session_id': self.session_id,
                    'minutes_used': minutes_used
                }
                
                try:
                    server_url = self._get_current_server_url()
                    async with self.session.post(f'{server_url}/api/logout', json=logout_data) as response:
                        if response.status == 200:
                            logger.info("Logout successful")
                        else:
                            logger.warning(f"Logout failed: {response.status}")
                except Exception as e:
                    logger.error(f"Logout error: {e}")
            
            # Force end locally
            self.session_active = False
            self.session_timer.stop()
            self.timer_overlay.hide()
            self._show_lock_screen()
            
            self.set_status('Session ended', False)
            
            self.tray.showMessage(
                '🎮 NetCafe Pro 2.0',
                'Gaming session ended. Computer locked.',
                QSystemTrayIcon.Information,
                3000
            )
            
        except Exception as e:
            logger.error(f"End session error: {e}")
    
    def _tick(self):
        if not self.session_active:
            return
        
        self.remaining_time -= 1
        
        # Warnings
        if self.remaining_time <= 300 and not self._notified_5min:
            self._notified_5min = True
            self.tray.showMessage(
                '⚠️ Time Warning',
                'Your gaming session will end in 5 minutes!',
                QSystemTrayIcon.Warning,
                5000
            )
        
        if self.remaining_time <= 60 and not self._notified_1min:
            self._notified_1min = True
            self.tray.showMessage(
                '🚨 Final Warning',
                'Your gaming session will end in 1 minute!',
                QSystemTrayIcon.Critical,
                5000
            )
        
        if self.remaining_time <= 0:
            asyncio.create_task(self._end_session())
            return
        
        self._update_timer()
    
    def _update_timer(self):
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        self.timer_overlay.set_time(time_str)
        self.tray.setToolTip(f'🎮 NetCafe Pro 2.0 - Time: {time_str}')
    
    def set_status(self, status, connected=False):
        self.lock_screen.set_connection_status(status, connected)
        self.timer_overlay.set_status(f'{"🟢" if connected else "🔴"} {status}')
        
        if hasattr(self, 'status_action'):
            self.status_action.setText(f'{"🟢" if connected else "🔴"} {status}')
        
        logger.info(f"Status: {status} (Connected: {connected})")
    
    async def _handle_ws_messages(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._process_ws_message(data)
                    except json.JSONDecodeError:
                        logger.error("Invalid WebSocket message")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.info("WebSocket closed")
                    break
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            self.ws = None
            self.set_status('Disconnected', False)
            self._start_reconnect_timer()
    
    async def _process_ws_message(self, data):
        msg_type = data.get('type')
        
        if msg_type == 'force_logout':
            QMessageBox.information(None, '⚠️ Session Ended', 
                                    data.get('message', 'Your session was ended by administrator.'))
            await self._end_session()
        
        elif msg_type == 'time_update':
            minutes = data.get('minutes', 0)
            if minutes > 0 and not self.session_active:
                await self.start_session(minutes)
    
    def _start_reconnect_timer(self):
        if not self.reconnect_timer.isActive() and self.reconnect_attempts < self.max_reconnect_attempts:
            delay = min(5000 + (self.reconnect_attempts * 3000), 20000)
            self.reconnect_timer.start(delay)
            logger.info(f"Reconnecting in {delay/1000}s")
    
    def _try_reconnect(self):
        logger.info("Attempting reconnection...")
        asyncio.create_task(self.connect_to_server())
        self.reconnect_timer.stop()
    
    def run(self):
        logger.info("Starting NetCafe Pro 2.0 Gaming Client")
        
        try:
            with self.loop:
                self.loop.create_task(self.connect_to_server())
                self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            self._cleanup()

def main():
    try:
        client = NetCafeClient()
        client.run()
    except Exception as e:
        logger.error(f"Failed to start client: {e}")
        input("Press Enter to exit...")

if __name__ == '__main__':
    main() 