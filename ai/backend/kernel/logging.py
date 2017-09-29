import logging
from logging.handlers import QueueHandler


class OutsockHandler(QueueHandler):
    def enqueue(self, record):
        msg = self.formatter.format(record)
        self.queue.write([
            b'stderr',
            (msg + '\n').encode('utf8'),
        ])


class BraceLogRecord(logging.LogRecord):
    def getMessage(self):
        if self.args is not None:
            return self.msg.format(*self.args)
        return self.msg


def setup_logger(outsock, log_prefix, debug):
    # configure logging to publish logs via outsock as well
    loghandlers = [logging.StreamHandler()]
    if not debug:
        loghandlers.append(OutsockHandler(outsock))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=log_prefix + ': {message}',
        style='{',
        handlers=loghandlers,
    )
    _factory = lambda *args, **kwargs: BraceLogRecord(*args, **kwargs)
    logging.setLogRecordFactory(_factory)
