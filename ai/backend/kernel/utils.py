from pathlib import Path


def find_executable(*paths):
    '''
    Find the first executable regular file in the given list of paths.
    '''
    for path in paths:
        if isinstance(path, (str, bytes)):
            path = Path(path)
        for child in path.iterdir():
            if child.is_file() and child.stat().st_mode & 0o100 != 0:
                return child
    return None
