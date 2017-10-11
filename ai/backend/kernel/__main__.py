'''
The kernel main program.
'''

import importlib
from . import lang_map, parse_args

cmdargs = parse_args()
cls_name = lang_map[cmdargs.lang]
imp_path, cls_name = cls_name.rsplit('.', 1)
mod = importlib.import_module(imp_path)
cls = getattr(mod, cls_name)
runner = cls()
runner.run(cmdargs)
