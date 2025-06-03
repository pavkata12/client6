#!/usr/bin/env python3
"""
Improved NetCafe Client
A modern client application for NetCafe management system
"""

import sys
import os
import asyncio
import json
import logging
from datetime import datetime
import socket
import platform
import uuid
from logging.handlers import RotatingFileHandler

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

class Config:
    """Configuration manager for the NetCafe client"""
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self):
        """Load configuration from file"""
        default_config = {
            "server": {
                "host": "localhost",
                "port": 8080,
                "websocket_endpoint": "/ws",
                "reconnect_interval": 5,
                "max_reconnect_attempts": 10
            },
            "client": {
                "computer_id": "",
                "auto_start": True,
                "minimize_to_tray": True,
                "show_timer_overlay": True,
                "timer_position": {"x": 200, "y": 40}
            },
            "security": {
                "block_windows_key": True,
                "block_ctrl_esc": True,
                "block_alt_f4": True,
                "full_screen_lock": True
            },
            "logging": {
                "level": "INFO",
                "file": "client.log",
                "max_size_mb": 10,
                "backup_count": 5
            },
            "ui": {
                "timer_font_size": 60,
                "status_font_size": 18,
                "timer_opacity": 0.9,
                "lock_screen_message": "Session not active",
                "notifications": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                self._merge_config(default_config, config)
                return default_config
            else:
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    
    def _merge_config(self, default, loaded):
        """Recursively merge loaded config with defaults"""
        for key, value in loaded.items():
            if key in default:
                if isinstance(value, dict) and isinstance(default[key], dict):
                    self._merge_config(default[key], value)
                else:
                    default[key] = value
    
    def save_config(self, config=None):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config or self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key_path, default=None):
        """Get config value using dot notation (e.g., 'server.host')"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, key_path, value):
        """Set config value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()

def setup_logging(config):
    """Setup logging with rotation"""
    log_level = getattr(logging, config.get('logging.level', 'INFO'))
    log_file = config.get('logging.file', 'client.log')
    max_size = config.get('logging.max_size_mb', 10) * 1024 * 1024
    backup_count = config.get('logging.backup_count', 5)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size, backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=[file_handler, console_handler]
    )
    
    return logging.getLogger(__name__)

if __name__ == '__main__':
    # Test the config system
    config = Config()
    logger = setup_logging(config)
    logger.info("Config and logging system initialized")
    print("Improved client architecture ready!") 