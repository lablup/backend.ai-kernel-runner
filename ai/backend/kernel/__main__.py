'''
The kernel main program.
'''

import argparse
import importlib

lang_map = {
    'python': 'ai.backend.kernel.python.Runner',
    'java': 'ai.backend.kernel.python.Runner',
    'c': 'ai.backend.kernel.c.Runner',
    'cpp': 'ai.backend.kernel.cpp.Runner',
    'rust': 'ai.backend.kernel.rust.Runner',
    'go': 'ai.backend.kernel.golang.Runner',
    'lua': 'ai.backend.kernel.lua.Runner',
}


parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', default=False)
parser.add_argument('lang', type=str, choices=lang_map.keys())
cmdargs = parser.parse_args()

cls_name = lang_map[cmdargs.lang]
imp_path, cls_name = cls_name.rsplit('.', 1)
mod = importlib.import_module(imp_path)
cls = getattr(mod, cls_name)
runner = cls()
runner.run(cmdargs)
