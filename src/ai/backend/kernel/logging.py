import logging
from logging.handlers import QueueHandler


class LogQHandler(QueueHandler):
    def enqueue(self, record):
        msg = self.formatter.format(record)
        self.queue.put_nowait((
            b'stderr',
            (msg + '\n').encode('utf8'),
        ))


class BraceLogRecord(logging.LogRecord):
    def getMessage(self):
        if self.args is not None:
            return self.msg.format(*self.args)
        return self.msg


def setup_logger(log_queue, log_prefix, debug):
    # configure logging to publish logs via outsock as well
    loghandlers = [logging.StreamHandler()]
    if not debug:
        loghandlers.append(LogQHandler(log_queue))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=log_prefix + ': {message}',
        style='{',
        handlers=loghandlers,
    )
    _factory = lambda *args, **kwargs: BraceLogRecord(*args, **kwargs)
    logging.setLogRecordFactory(_factory)
