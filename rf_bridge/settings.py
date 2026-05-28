"""Persistent UI settings for RF Bridge."""

import os
from PySide6.QtCore import QSettings


class AppSettings:
    def __init__(self):
        self.settings = QSettings("RF Bridge", "RF Bridge")

    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)

    def get_bool(self, key, default=False):
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_float(self, key, default):
        value = self.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_bytes(self, key):
        return self.get(key, None)

    def default_storage_root(self):
        return os.path.join(os.path.expanduser("~"), "Documents", "RF Bridge")

    def get_storage_root(self):
        return self.get("storage_root", self.default_storage_root())

    def set_storage_root(self, path):
        self.set("storage_root", path)

    def get_appearance(self):
        return str(self.get("appearance", "Dark"))

    def set_appearance(self, appearance):
        self.set("appearance", appearance)


    def get_filename_time_format(self):
        return str(self.get("filename_time_format", "12-hour"))

    def set_filename_time_format(self, time_format):
        self.set("filename_time_format", time_format)
