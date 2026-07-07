"""Logger factory and global logging configuration."""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def _resolve_log_dir() -> Path:
    """Resolve the directory where log files will be written.

    Precedence: (1) the ``BIOSEQ_DL_LOG_DIR`` env var if set, (2) the
    ``bioseq_dl.core.config`` cache log path if available, (3) ``~/.cache/bioseq_dl/logs``.

    Returns:
        Path: The resolved log directory.

    """
    env_dir = os.environ.get("BIOSEQ_DL_LOG_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # Optional: use project config if available (avoids a hard dependency)
    with contextlib.suppress(Exception):
        from bioseq_dl.core import config  # ty: ignore  # type: ignore[import]  # noqa: PLC0415

        cfg = config.get_config()
        return Path(cfg.cache_paths.logs()).expanduser().resolve()

    return Path("~/.cache/bioseq_dl/logs").expanduser().resolve()


class _LoggingManager:
    """Configure root logging once and hand out child loggers that propagate to the root handlers.

    Handlers (console/file) are installed on the ROOT logger; child loggers
    propagate so their messages reach the root handlers.
    """

    def __init__(self) -> None:
        """Initialize default logging settings (unconfigured until first use)."""
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
        enable: bool | None = None,
        level: int | None = None,
        log_dir: os.PathLike[str] | str | None = None,
        fmt: str | None = None,
        datefmt: str | None = None,
        use_rotation: bool | None = None,
        filename: str | None = None,
    ) -> None:
        """Update the global logging configuration.

        Changes are applied lazily (on the next logger access). If ``log_dir`` is not
        provided, the directory is re-resolved so a runtime change to
        ``BIOSEQ_DL_LOG_DIR`` is honored (useful for pytest fixtures). The same env
        var can also disable logging entirely.

        Args:
            enable (bool | None): Whether logging is enabled; unchanged if None.
            level (int | None): Root/console log level; unchanged if None.
            log_dir (os.PathLike[str] | str | None): Log directory; re-resolved if None.
            fmt (str | None): Log record format string; unchanged if None.
            datefmt (str | None): Date format string; unchanged if None.
            use_rotation (bool | None): Whether to use a timed rotating file handler.
            filename (str | None): Log file name; unchanged if None.

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
        """Build console and (optional) file handlers for the ROOT logger.

        Falls back to console-only if the file handler cannot be created.

        Returns:
            list[logging.Handler]: The handlers to attach to the root logger.

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
        except Exception as e:  # noqa: BLE001  # defensive catch-all
            # Keep console even if the file handler fails; print a clear hint.
            with contextlib.suppress(Exception):
                sys.stderr.write(
                    f"[bioseq_dl.logging] WARNING: Failed to initialize file handler at "
                    f"{self._log_dir!s} ({type(e).__name__}: {e}). Falling back to console only.\n"
                )

        return handlers

    def _install_root_handlers(self) -> None:
        """(Re)install handlers on the ROOT logger exactly once per configuration."""
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
        """Install root handlers on first use after a (re)configuration."""
        if not self._configured:
            self._install_root_handlers()
            self._configured = True


_manager = _LoggingManager()


def configure_logging(
    *,
    enable: bool | None = None,
    level: int | None = None,
    log_dir: os.PathLike[str] | str | None = None,
    fmt: str | None = None,
    datefmt: str | None = None,
    use_rotation: bool | None = None,
    filename: str | None = None,
) -> None:
    """Configure bioseq_dl logging once at program start (optional).

    Also quiets ``zeep`` and ``urllib3`` to WARNING. Changes are applied lazily on
    the next ``get_logger`` call.

    Args:
        enable (bool | None): Whether logging is enabled; unchanged if None.
        level (int | None): Root/console log level; unchanged if None.
        log_dir (os.PathLike[str] | str | None): Log directory; re-resolved if None.
        fmt (str | None): Log record format string; unchanged if None.
        datefmt (str | None): Date format string; unchanged if None.
        use_rotation (bool | None): Whether to use a timed rotating file handler.
        filename (str | None): Log file name; unchanged if None.

    """
    # Deactivate zeep and urllib3 logging by default
    logging.getLogger("zeep").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    _manager.configure(
        enable=enable,
        level=level,
        log_dir=log_dir,
        fmt=fmt,
        datefmt=datefmt,
        use_rotation=use_rotation,
        filename=filename,
    )


LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def setup_logging(level: str = "info") -> None:
    """Configure logging from a CLI level string (default INFO) and apply it now.

    ``configure_logging`` only marks the manager dirty (handlers are reinstalled
    lazily on the next ``get_logger``). CLI commands that use module-level loggers
    created at import time would otherwise never pick up the new level, so we force
    the root handlers to be (re)installed immediately.

    Args:
        level (str): Log level name (``debug``/``info``/``warning``/``error``/``critical``);
            unknown values fall back to INFO.

    """
    configure_logging(level=LOG_LEVELS.get(level.lower(), logging.INFO))
    _manager._ensure_configured()  # noqa: SLF001  # apply eagerly for the CLI


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger for the current module/class.

    Children keep level=NOTSET to inherit the root's effective level.

    Args:
        name (str | None): Logger name; the root logger is used when None.

    Returns:
        logging.Logger: A configured logger that propagates to the root handlers.

    """
    _manager._ensure_configured()  # noqa: SLF001  # module logging singleton
    logger = logging.getLogger(name or "")
    logger.disabled = not _manager._enable  # noqa: SLF001  # module logging singleton
    logger.setLevel(logging.NOTSET)  # <-- inherit from root
    logger.propagate = True
    return logger
