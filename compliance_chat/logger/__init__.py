
from .custom_logger import CustomLogger as _CustomLogger  # backward compat
try:
    from .custom_logger import CustomLogger
except Exception:
    CustomLogger = _CustomLogger

# Expose a global structlog-style logger used across the codebase
GLOBAL_LOGGER = CustomLogger().get_logger(__name__)

def safe_print(*args, **kwargs):
    """Prints to stdout safely handling encoding issues on Windows."""
    try:
        print(*args, **kwargs)
    except OSError as e:
        if e.errno == 22:
            try:
                # Fallback to pure ASCII if UTF-8 fails
                safe_args = [str(arg).encode('ascii', 'ignore').decode('ascii') for arg in args]
                print(*safe_args, **kwargs)
            except Exception:
                pass
        else:
            pass
    except Exception:
        pass
