"""setup_logger: Structured JSON logging with colored console output.

Configures a logger that outputs:
- JSON formatted logs to rotating file handlers (for log aggregation)
- Colored console output (for development visibility)

Supports log rotation by file size and automatic log level configuration.

Dependencies:
- colorlog (for colored console output)
- python-json-logger (for JSON file output)

Usage:
    logger = setup_logger('my_module', level='INFO', log_file='logs/my.log')
    logger.info('Hello, world!')
    logger.error('Something went wrong', exc_info=True)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """Configure a structured logger with file and console handlers.
    
    Parameters
    ----------
    name : str
        Logger name (typically module name).
    level : str, default 'INFO'
        Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    log_file : str, optional
        Path to log file. If None, no file handler is created.
    max_bytes : int, default 10MB
        Maximum log file size before rotation.
    backup_count : int, default 5
        Number of backup log files to keep.
    console : bool, default True
        Whether to add a console handler.
    
    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Create formatters
    json_formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    )
    
    # Console handler with colors (if colorlog available)
    if console:
        try:
            import colorlog
            console_formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s%(reset)s",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        except ImportError:
            # Fallback to plain console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
            logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
    
    return logger
