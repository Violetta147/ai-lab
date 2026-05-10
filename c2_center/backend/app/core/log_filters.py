"""Custom log filters for the C2 backend."""

import logging


class HealthLogFilter(logging.Filter):
    """Suppress noisy /api/health access log lines from uvicorn."""

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access formats: '... "GET /api/health HTTP/1.1" 200'
        try:
            if record.args and len(record.args) >= 3:
                path = record.args[2]
                if isinstance(path, str) and "/api/health" in path:
                    return False
        except Exception:
            pass
        return True
