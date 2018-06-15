import asyncio
from pathlib import Path

__all__ = (
    'current_loop',
    'find_executable',
)


if hasattr(asyncio, 'get_running_loop'):
    current_loop = asyncio.get_running_loop
else:
    current_loop = asyncio.get_event_loop


def find_executable(*paths):
    '''
    Find the first executable regular file in the given list of paths.
    '''
    for path in paths:
        if isinstance(path, (str, bytes)):
            path = Path(path)
        if not path.exists():
            continue
        for child in path.iterdir():
            if child.is_file() and child.stat().st_mode & 0o100 != 0:
                return child
    return None


async def safe_close_task(task):
    if task is not None and not task.done():
        task.cancel()
        await task
