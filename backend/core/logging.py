import logging


class SafeErrorFilter(logging.Filter):
    """Production error logs identify the failure without dumping request data or SQL values."""
    def filter(self, record):
        if record.levelno >= logging.ERROR:
            kind = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else "Error"
            record.msg = "Request failed (%s), status %s"
            record.args = (kind, getattr(record, "status_code", 500))
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True
