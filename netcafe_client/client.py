import sys
import os
import asyncio
import json
import logging
from datetime import datetime
import socket
import platform
import uuid

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, 
    QMenu, QPushButton, QLineEdit, QMessageBox, QDialog, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QAction
import qasync
import aiohttp
import win32con
import win32api
import win32gui
import win32process
import threading
import ctypes
from qasync import asyncSlot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='client.log'
)
logger = logging.getLogger(__name__)

# Constants
SERVER_CONFIG = 'client_config.json'
DEFAULT_SERVER_PORT = 8765
DEFAULT_SERVER_HOST = 'localhost'

class TimerOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle('Session Timer')
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel('', self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            'background: rgba(0,0,0,0.7); color: white; font-size: 60px; border-radius: 24px; padding: 40px 0px;'
        )
        layout.addWidget(self.label)
        
        self.status_label = QLabel('', self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: white; font-size: 18px; margin-top: 8px;')
        layout.addWidget(self.status_label)
        
        btn_layout = QHBoxLayout()
        
        self.min_btn = QPushButton('Minimize to tray', self)
        self.min_btn.setStyleSheet('font-size: 18px; padding: 8px 24px;')
        btn_layout.addWidget(self.min_btn)
        
        self.end_btn = QPushButton('End Session', self)
        self.end_btn.setStyleSheet('font-size: 18px; padding: 8px 24px; background: #ff4444; color: white;')
        btn_layout.addWidget(self.end_btn)
        
        layout.addLayout(btn_layout)
        
        self.resize(800, 200)
        self.move(200, 40)

class BlankScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet('background-color: #111;')
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel('Session not active', self)
        self.label.setStyleSheet('color: white; font-size: 36px;')
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.status_label = QLabel('', self)
        self.status_label.setStyleSheet('color: #aaa; font-size: 22px; margin-top: 24px;')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
    
    def show_blank(self, msg='Session not active', status=''):
        self.label.setText(msg)
        self.status_label.setText(status)
        self.showFullScreen()
        self.raise_()
    
    def hide_blank(self):
        self.hide()
    
    def set_status(self, status):
        self.status_label.setText(status)

class KeyboardBlocker:
    def __init__(self):
        self.hooked = None
        self.enabled = False
    
    def install(self):
        if self.hooked:
            return
        
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
        
        def low_level_keyboard_proc(nCode, wParam, lParam):
            if nCode == 0:
                vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong * 6))[0][0]
                if vk_code in (0x5B, 0x5C):  # VK_LWIN, VK_RWIN
                    return 1
                if vk_code == 0x1B and (win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000):  # VK_ESCAPE
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
    
    def uninstall(self):
        if self.hooked:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hooked)
            self.hooked = None
            self.enabled = False

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Login')
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Username')
        layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Password')
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        
        self.login_btn = QPushButton('Login')
        self.login_btn.clicked.connect(self.try_login)
        layout.addWidget(self.login_btn)
        
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint)
        self.accepted = False
    
    def try_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Please enter both username and password')
            return
        self.accepted = True
        self.accept()
    
    def get_credentials(self):
        return self.username_input.text(), self.password_input.text()

class NetCafeClient:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.loop = qasync.QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)
        
        self.overlay = TimerOverlay()
        self.blank = BlankScreen()
        self.keyboard_blocker = KeyboardBlocker()
        
        self.session_active = False
        self.remaining_time = 0
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self._tick)
        self.connection_status = 'Disconnected'
        
        self.session = None
        self.ws = None
        self.user_id = None
        self.computer_id = self._get_computer_id()
        
        self._init_tray()
        self.overlay.min_btn.clicked.connect(self.overlay.hide)
        self.overlay.end_btn.clicked.connect(self.end_session)
        self._show_blank()
        
        self._notified_5min = False
        self._notified_1min = False
    
    def _get_computer_id(self):
        try:
            mac = uuid.getnode()
            return f"PC-{mac:012x}"
        except:
            return f"PC-{socket.gethostname()}"
    
    def _init_tray(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.tray = QSystemTrayIcon(QIcon(icon_path))
        self.tray.setToolTip('NetCafe Client')
        
        menu = QMenu()
        show_action = QAction('Show Timer')
        hide_action = QAction('Hide Timer')
        quit_action = QAction('Exit')
        
        show_action.triggered.connect(self._show_overlay)
        hide_action.triggered.connect(self.overlay.hide)
        quit_action.triggered.connect(self._exit)
        
        menu.addAction(show_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
    
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.overlay.isVisible():
                self.overlay.hide()
            else:
                self._show_overlay()
    
    def _exit(self):
        self.session_timer.stop()
        self.keyboard_blocker.uninstall()
        if self.session:
            asyncio.create_task(self.session.close())
        self.tray.hide()
        self.app.quit()
    
    def _get_server_config(self):
        if os.path.exists(SERVER_CONFIG):
            with open(SERVER_CONFIG, 'r') as f:
                return json.load(f)
        
        from PySide6.QtWidgets import QInputDialog
        host, ok = QInputDialog.getText(
            None, 
            "Server Address", 
            "Enter the server address:",
            text=DEFAULT_SERVER_HOST
        )
        
        if not ok or not host:
            QMessageBox.critical(None, "No Address", "No server address entered. Exiting.")
            self.app.quit()
            return {}
        
        config = {'host': host, 'port': DEFAULT_SERVER_PORT}
        with open(SERVER_CONFIG, 'w') as f:
            json.dump(config, f)
        
        return config
    
    async def connect_to_server(self):
        config = self._get_server_config()
        if not config:
            return
        
        try:
            self.session = aiohttp.ClientSession()
            
            if not await self.authenticate():
                return
            
            ws_url = f"ws://{config['host']}:{config['port']}/ws"
            self.ws = await self.session.ws_connect(ws_url)
            
            asyncio.create_task(self._handle_ws_messages())
            
            self.set_connection_status('Connected')
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self.set_connection_status('Connection failed')
            if self.session:
                await self.session.close()
                self.session = None
    
    async def authenticate(self):
        dialog = LoginDialog()
        if not dialog.exec():
            return False
        
        username, password = dialog.get_credentials()
        
        try:
            async with self.session.post(
                f"http://{self._get_server_config()['host']}:{self._get_server_config()['port']}/api/auth",
                json={'username': username, 'password': password}
            ) as response:
                data = await response.json()
                
                if not data['success']:
                    QMessageBox.warning(None, 'Error', data['message'])
                    return False
                
                self.user_id = data['user']['id']
                return True
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            QMessageBox.critical(None, 'Error', 'Failed to connect to server')
            return False
    
    async def _handle_ws_messages(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._process_ws_message(data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.ws.exception()}")
                    break
        except Exception as e:
            logger.error(f"WebSocket handler error: {str(e)}")
        finally:
            self.ws = None
            self.set_connection_status('Disconnected')
    
    async def _process_ws_message(self, data):
        msg_type = data.get('type')
        
        if msg_type == 'session_update':
            sessions = data.get('sessions', [])
            for session in sessions:
                if session['computer_id'] == self.computer_id:
                    self.start_session(session['duration_minutes'])
                    break
    
    def _show_blank(self):
        self.blank.show_blank()
        self.keyboard_blocker.install()
    
    def _show_overlay(self):
        self.overlay.show()
        self.overlay.raise_()
    
    @asyncSlot()
    async def start_session(self, duration):
        if not self.session or not self.user_id:
            return
        
        try:
            async with self.session.post(
                f"http://{self._get_server_config()['host']}:{self._get_server_config()['port']}/api/session/start",
                json={
                    'user_id': self.user_id,
                    'computer_id': self.computer_id,
                    'duration_minutes': duration
                }
            ) as response:
                data = await response.json()
                
                if not data['success']:
                    QMessageBox.warning(None, 'Error', data['message'])
                    return
                
                self.session_active = True
                self.remaining_time = duration * 60
                self.session_timer.start(1000)
                self._notified_5min = False
                self._notified_1min = False
                
                self.blank.hide_blank()
                self._show_overlay()
                self._update_timer()
                
        except Exception as e:
            logger.error(f"Start session error: {str(e)}")
            QMessageBox.critical(None, 'Error', 'Failed to start session')
    
    @asyncSlot()
    async def end_session(self):
        if not self.session or not self.user_id:
            return
        
        try:
            async with self.session.post(
                f"http://{self._get_server_config()['host']}:{self._get_server_config()['port']}/api/session/end",
                json={'user_id': self.user_id}
            ) as response:
                data = await response.json()
                
                if not data['success']:
                    QMessageBox.warning(None, 'Error', data['message'])
                    return
                
                self.session_active = False
                self.session_timer.stop()
                self.overlay.hide()
                self._show_blank()
                
        except Exception as e:
            logger.error(f"End session error: {str(e)}")
            QMessageBox.critical(None, 'Error', 'Failed to end session')
    
    def _tick(self):
        if not self.session_active:
            return
        
        self.remaining_time -= 1
        
        if self.remaining_time <= 300 and not self._notified_5min:
            self._notified_5min = True
            self.tray.showMessage(
                'Session Ending',
                'Your session will end in 5 minutes',
                QSystemTrayIcon.Warning,
                5000
            )
        
        if self.remaining_time <= 60 and not self._notified_1min:
            self._notified_1min = True
            self.tray.showMessage(
                'Session Ending',
                'Your session will end in 1 minute',
                QSystemTrayIcon.Critical,
                5000
            )
        
        if self.remaining_time <= 0:
            self.session_timer.stop()
            self.session_active = False
            self.overlay.hide()
            self._show_blank()
            return
        
        self._update_timer()
    
    def _update_timer(self):
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        self.overlay.set_time(f"{minutes:02d}:{seconds:02d}")
    
    def set_connection_status(self, status):
        self.connection_status = status
        self.overlay.set_status(status)
        self.blank.set_status(status)
    
    def run(self):
        # Use qasync event loop for PySide6
        with self.loop:
            self.loop.create_task(self.connect_to_server())
            self.loop.run_forever()

def main():
    client = NetCafeClient()
    client.run()

if __name__ == '__main__':
    main() 