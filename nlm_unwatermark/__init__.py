"""nlm-unwatermark: removes the NotebookLM watermark from PDF, PPTX, and image files."""

# tqdm defaults to backing its write lock with multiprocessing.RLock() "for
# multiprocessing safety", even though this tool is single-process. That
# lock's semaphore is registered with multiprocessing.resource_tracker,
# whose cleanup helper is spawned via sys.executable. In a PyInstaller
# onefile build sys.executable is the frozen binary itself rather than a
# real Python interpreter, so that respawn crashes at process exit. Setting
# mp_lock up front makes tqdm skip creating it (see
# tqdm.std.TqdmDefaultWriteLock.create_mp_lock), which we never need.
from tqdm.std import TqdmDefaultWriteLock as _TqdmDefaultWriteLock

_TqdmDefaultWriteLock.mp_lock = None

__version__ = "1.0.0"
