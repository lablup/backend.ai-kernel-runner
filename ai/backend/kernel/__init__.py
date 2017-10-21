import argparse

from .base import BaseRunner
from .terminal import Terminal


__all__ = (
    'BaseRunner',
    'Terminal',
)

lang_map = {
    'python': 'ai.backend.kernel.python.Runner',
    'c': 'ai.backend.kernel.c.Runner',
    'cpp': 'ai.backend.kernel.cpp.Runner',
    'golang': 'ai.backend.kernel.golang.Runner',
    'rust': 'ai.backend.kernel.rust.Runner',
    'java': 'ai.backend.kernel.java.Runner',
    'haskell': 'ai.backend.kernel.haskell.Runner',
    'julia': 'ai.backend.kernel.julia.Runner',
    'lua': 'ai.backend.kernel.lua.Runner',
    'nodejs': 'ai.backend.kernel.nodejs.Runner',
    'octave': 'ai.backend.kernel.octave.Runner',
    'php': 'ai.backend.kernel.php.Runner',
    'r': 'ai.backend.kernel.r.Runner',
    'git': 'ai.backend.kernel.git.Runner',
}


def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('lang', type=str, choices=lang_map.keys())
    return parser.parse_args(args)
