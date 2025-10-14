from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def _resolve_log_dir() -> Path:
    """
    Resolve the directory where log files will be written.

    Precedence
    ----------
    1) BIOSEQ_DL_LOG_DIR env var (if set)
    2) bioseq_dl.core.config cache log path (if available)
    3) ~/.cache/bioseq_dl/logs
    """
    env_dir = os.environ.get("BIOSEQ_DL_LOG_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    try:
        # Optional: use project config if available
        from bioseq_dl.core import config  # type: ignore
        cfg = config.get_config()
        return Path(cfg.cache_paths.logs()).expanduser().resolve()
    except Exception:
        pass

    return Path("~/.cache/bioseq_dl/logs").expanduser().resolve()


class _LoggingManager:
    """
    Singleton-like manager that configures root logging once and
    exposes a small API for obtaining child loggers and adjusting settings.

    Key points
    ----------
    - Handlers (console/file) are installed on the ROOT logger.
    - Child loggers PROPAGATE so their messages reach the root handlers.
    """

    def __init__(self) -> None:
        self._configured = False
        self._enable = True
        self._level = logging.INFO
        self._log_dir = _resolve_log_dir()
        self._fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        self._datefmt = "%Y-%m-%d %H:%M:%S"
        self._use_rotation = True
        self._filename = "bioseq_dl.log"

    def configure(
        self,
        *,
        enable: Optional[bool] = None,
        level: Optional[int] = None,
        log_dir: Optional[os.PathLike[str] | str] = None,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_rotation: Optional[bool] = None,
        filename: Optional[str] = None,
    ) -> None:
        """
        Update the global logging configuration. Changes are applied lazily
        (on the next logger access).

        Notes
        -----
        If `log_dir` is not provided, we re-resolve the directory so that any
        runtime change to BIOSEQ_DL_LOG_DIR is honored (useful for pytest fixtures).
        """
        if enable is not None:
            self._enable = bool(enable)
        if level is not None:
            self._level = level

        # Re-evaluate log_dir on each configure() call if not explicitly provided,
        # so that env var BIOSEQ_DL_LOG_DIR set at runtime takes effect.
        if log_dir is not None:
            self._log_dir = Path(log_dir).expanduser().resolve()
        else:
            self._log_dir = _resolve_log_dir()

        if fmt is not None:
            self._fmt = fmt
        if datefmt is not None:
            self._datefmt = datefmt
        if use_rotation is not None:
            self._use_rotation = bool(use_rotation)
        if filename is not None:
            self._filename = filename

        # Environment override for disabling logging
        env_flag = os.environ.get("BIOSEQ_DL_LOGGING", "").strip().lower()
        if env_flag in {"0", "false", "off", "no"}:
            self._enable = False

        self._configured = False

    def _build_handlers(self) -> list[logging.Handler]:
        """
        Build console + (optional) file handlers for the ROOT logger.
        """
        formatter = logging.Formatter(self._fmt, self._datefmt)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(self._level)
        ch.setFormatter(formatter)

        handlers: list[logging.Handler] = [ch]

        # File handler
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self._log_dir / self._filename

            if self._use_rotation:
                from logging.handlers import TimedRotatingFileHandler
                fh = TimedRotatingFileHandler(
                    filename=str(log_path),
                    when="D",
                    interval=1,
                    backupCount=7,
                    encoding="utf-8",
                )
            else:
                fh = logging.FileHandler(str(log_path), encoding="utf-8")

            # Persist everything to file; console can be less verbose
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            handlers.append(fh)
        except Exception as e:
            # Keep console even if the file handler fails; print a clear hint.
            try:
                sys.stderr.write(
                    f"[bioseq_dl.logging] WARNING: Failed to initialize file handler at "
                    f"{self._log_dir!s} ({type(e).__name__}: {e}). Falling back to console only.\n"
                )
            except Exception:
                pass

        return handlers

    def _install_root_handlers(self) -> None:
        """
        (Re)install handlers on the ROOT logger exactly once per configuration.
        """
        root = logging.getLogger()
        root.handlers.clear()

        if not self._enable:
            root.disabled = True
            return

        root.disabled = False
        root.setLevel(self._level)
        for h in self._build_handlers():
            root.addHandler(h)
        # root has no parent; no need to set propagate.

    def _ensure_configured(self) -> None:
        if not self._configured:
            self._install_root_handlers()
            self._configured = True

    # ---------------- Public API ----------------

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        Return a logger. Child loggers PROPAGATE so their messages reach
        the root handlers configured here.
        """
        self._ensure_configured()
        logger = logging.getLogger(name if name else "")
        logger.disabled = not self._enable
        logger.setLevel(self._level)
        logger.propagate = True  # <-- critical: let messages reach root handlers
        return logger

    def set_level(self, level: int) -> None:
        """Set the global logging level and trigger reconfiguration."""
        self._level = level
        self._configured = False

    def enable(self, enable: bool = True) -> None:
        """Enable/disable logging globally and trigger reconfiguration."""
        self._enable = enable
        self._configured = False


_manager = _LoggingManager()


def configure_logging(
    *,
    enable: Optional[bool] = None,
    level: Optional[int] = None,
    log_dir: Optional[os.PathLike[str] | str] = None,
    fmt: Optional[str] = None,
    datefmt: Optional[str] = None,
    use_rotation: Optional[bool] = None,
    filename: Optional[str] = None,
) -> None:
    """
    Configure bioseq_dl logging once at program start (optional).
    """
    _manager.configure(
        enable=enable,
        level=level,
        log_dir=log_dir,
        fmt=fmt,
        datefmt=datefmt,
        use_rotation=use_rotation,
        filename=filename,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a logger for the current module/class.
    Children should keep level=NOTSET to inherit the root's effective level.
    """
    _manager._ensure_configured()
    logger = logging.getLogger(name if name else "")
    logger.disabled = not _manager._enable
    logger.setLevel(logging.NOTSET)  # <-- inherit from root
    logger.propagate = True
    return logger


def set_level(level: int) -> None:
    """Update the global logging level (e.g., logging.DEBUG)."""
    _manager.set_level(level)


def enable_logging(enable: bool = True) -> None:
    """Enable or disable logging globally (same as BIOSEQ_DL_LOGGING=0)."""
    _manager.enable(enable)