# This file will replace the logger.py file in each target repository

import json
import logging
import os
from logging import Formatter, Logger, LogRecord, StreamHandler
from logging.handlers import MemoryHandler
from typing import Dict, Optional

# Remove the extra handler(s) that AWS attaches when running in lambda to prevent
# duplicate log messages in our own logging handler
ROOT_LOGGER = logging.getLogger()
AWS_HANDLERS = ROOT_LOGGER.handlers.copy()


class DelayedJSONStreamHandler(MemoryHandler):
    """A handler class which buffers logging records in memory, flushing them to a
    target handler only when the program exits or flushing is triggered manually. When
    the buffer is flushed, a single json blob is emitted containing all the logged
    messages and additional context that is passed to the handler constructor.
    """

    def __init__(
        self,
        target: Optional[StreamHandler] = None,
        context: Optional[Dict] = None,
        **kwargs
    ):
        """Initializes a `DelayedJSONStreamHandler`. If `target` is not provided at
        initialization, it must be provided later, otherwise no records will be emitted.

        Args:
            target (StreamHandler, optional): The handler used to format log messages
            within the JSON output structure. Must be a StreamHandler. Defaults to None.
            context (Dict, optional): Additional context to prepend to the output JSON
            blob. Defaults to `dict()`.
        """

        super().__init__(
            capacity=int(1e7),
            target=target,
            flushOnClose=False,
        )

        if context is None:
            context = dict()

        self.context = context

    def shouldFlush(self, record: LogRecord) -> bool:
        return False  # Don't flush the buffer automatically

    def flush(self, context: Optional[Dict] = None) -> None:
        """Ensure that all logging calls have been flushed. This method is automatically
        called when the program exits, but may be called earlier as well.
        """

        # Add the AWS Handler(s) back so that the flushed message can be shown in the
        # CloudWatch logs
        if len(ROOT_LOGGER.handlers) == 1:
            for handler in AWS_HANDLERS:
                ROOT_LOGGER.addHandler(handler)

        if context is None:
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
                self.target.stream.write(dumped + self.target.terminator)  # type: ignore
                self.target.stream.flush()  # type: ignore
                self.buffer = []
        finally:
            self.release()


def configure_logger(logger: Logger, context: Optional[Dict] = None):
    if context is None:
        context = dict()

    # Log level for all other packages
    ROOT_LOGGER.setLevel(os.environ.get("ROOT_LOG_LEVEL", "INFO"))
    for handler in ROOT_LOGGER.handlers:
        ROOT_LOGGER.removeHandler(handler)

    # Log level for this package
    logger.setLevel(os.environ.get("LOG_LEVEL", "DEBUG"))

    # Log level for anything installed in tsdat
    logging.getLogger("tsdat").setLevel(os.environ.get("TSDAT_LOG_LEVEL", "INFO"))

    # Add buffered logger so all messages are output in one message in CloudWatch
    target = logging.StreamHandler()
    target.setFormatter(
        Formatter("[%(asctime)s: %(pathname)s %(levelname)s] %(message)s")
    )
    dmh = DelayedJSONStreamHandler(target=target, context=context)
    ROOT_LOGGER.addHandler(dmh)


def get_log_message(*args, **kwargs):
    raise NotImplementedError(
        "This method is kept only for backwards compatibility and should not be used."
    )
