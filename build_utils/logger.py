# TODO: This file will replace the logger.py file in each target repository

import os
import json
import logging

from logging import Formatter, LogRecord, StreamHandler, Logger
from logging.handlers import MemoryHandler
from typing import Dict


logger = logging.getLogger(__name__)


class DelayedJSONStreamHandler(MemoryHandler):
    """A handler class which buffers logging records in memory, flushing them to a
    target handler only when the program exits or flushing is triggered manually. When
    the buffer is flushed, a single json blob is emitted containing all the logged
    messages and additional context that is passed to the handler constructor.
    """

    def __init__(self, target: StreamHandler = None, context: Dict = None, **kwargs):
        """Initializes a `DelayedJSONStreamHandler`. If `target` is not provided at
        initialization, it must be provided later, otherwise no records will be emitted.

        Args:
            target (StreamHandler, optional): The handler used to format log messages
            within the JSON output structure. Must be a StreamHandler. Defaults to None.
            context (Dict, optional): Additional context to prepend to the output JSON
            blob. Defaults to `dict()`.
        """

        super().__init__(
            capacity=1e7,
            target=target,
            flushOnClose=False,
        )

        if context is None:
            context = dict()

        self.context = context

    def shouldFlush(self, record: LogRecord) -> bool:
        return False  # Don't flush the buffer automatically

    def flush(self, context: Dict = None) -> None:
        """Ensure that all logging calls have been flushed. This method is automatically
        called when the program exits, but may be called earlier as well.
        """
        if context == None:
            context = dict()

        self.context.update(context)

        self.acquire()
        try:
            if self.buffer and self.target:
                # Build json string
                log_dict = {
                    "context": self.context,
                    "logs": [self.target.format(record) for record in self.buffer],
                }
                dumped = json.dumps(log_dict)

                # Use the target
                self.target.stream.write(dumped + self.target.terminator)
                self.target.stream.flush()
                self.buffer = []
        finally:
            self.release()


def configure_logger(logger: Logger, context: Dict = None):
    if not context:
        context = dict()

    # Log level for all other packages
    root = logging.getLogger()
    root.setLevel(os.environ.get("ROOT_LOG_LEVEL", "INFO"))

    # Log level for anything installed in tsdat
    tsdat_logger = logging.getLogger("tsdat")
    tsdat_logger.setLevel(os.environ.get("TSDAT_LOG_LEVEL", "INFO"))

    # Log level for this file
    logger.setLevel(os.environ.get("LOG_LEVEL", "DEBUG"))

    target = logging.StreamHandler()
    target.setFormatter(
        Formatter("[%(asctime)s: %(pathname)s %(levelname)s] %(message)s")
    )

    dmh = DelayedJSONStreamHandler(target=target, context=context)

    root.addHandler(dmh)


def get_log_message(*args, **kwargs):
    raise NotImplementedError(
        "This method is kept only for backwards compatibility and should not be used."
    )

