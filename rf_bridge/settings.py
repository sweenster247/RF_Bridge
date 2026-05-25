"""Persistent UI settings for RF Bridge."""

from PySide6.QtCore import QSettings


class AppSettings:
    def __init__(self):
        self.settings = QSettings("RF Bridge", "RF Bridge")

    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)

    def get_float(self, key, default):
        value = self.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_bytes(self, key):
        return self.get(key, None)
