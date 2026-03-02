import logging

class Log:
    """Simple logging utility wrapping Python's `logging` module.

    If `filename` is provided the log directory will be created and filehandler added.
    """

    def __init__(self, name: str = "app", level: int = logging.INFO, filename: str | None = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # stream handler for console output
        ch = logging.StreamHandler()
        ch.setLevel(level)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        ch.setFormatter(fmt)
        self.logger.addHandler(ch)

        # optional file handler
        if filename:
            # ensure directory exists
            import os
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            fh = logging.FileHandler(filename)
            fh.setLevel(level)
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def set_level(self, level: int) -> None:
        self.logger.setLevel(level)
