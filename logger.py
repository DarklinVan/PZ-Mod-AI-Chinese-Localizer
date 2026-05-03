import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).parent / 'logs'

_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARN,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
}


class TextFormatter(logging.Formatter):
    def format(self, record):
        ts = datetime.datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        msg = record.getMessage()
        if record.exc_info and record.exc_info[0]:
            msg += '\n' + self.formatException(record.exc_info)
        return f'[{ts}] [{record.levelname}] [{record.funcName}] {msg}'


class _Logger:
    _instance = None

    def __init__(self):
        self._logger = None
        self._level = logging.INFO
        self._setup()

    def _setup(self):
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
            self._level = _LEVEL_MAP.get(level_name, logging.INFO)

            self._logger = logging.getLogger('pzlocalize')
            self._logger.setLevel(self._level)
            self._logger.handlers.clear()

            file_handler = RotatingFileHandler(
                LOG_DIR / 'app.log',
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
            )
            file_handler.setLevel(self._level)
            file_handler.setFormatter(TextFormatter())
            self._logger.addHandler(file_handler)

        except Exception:
            self._logger = None

    def debug(self, msg, *args, **kwargs):
        try:
            if self._logger:
                self._logger.debug(msg, *args, stacklevel=2, **kwargs)
        except Exception:
            pass

    def info(self, msg, *args, **kwargs):
        try:
            if self._logger:
                self._logger.info(msg, *args, stacklevel=2, **kwargs)
        except Exception:
            pass

    def warn(self, msg, *args, **kwargs):
        try:
            if self._logger:
                self._logger.warning(msg, *args, stacklevel=2, **kwargs)
        except Exception:
            pass

    def error(self, msg, *args, **kwargs):
        exc_info = kwargs.pop('exc_info', False)
        try:
            if self._logger:
                self._logger.error(msg, *args, exc_info=exc_info, stacklevel=2, **kwargs)
        except Exception:
            pass

    def set_level(self, level_name):
        level = _LEVEL_MAP.get(level_name.upper(), logging.INFO)
        self._level = level
        if self._logger:
            self._logger.setLevel(level)
            for h in self._logger.handlers:
                h.setLevel(level)

    @property
    def level_name(self):
        for name, val in _LEVEL_MAP.items():
            if val == self._level:
                return name
        return 'INFO'


logger = _Logger()
