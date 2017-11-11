from pathlib import Path
import re

import pytest


def test_setup_has_all_kernel_subpkgs():
    root = Path(__file__).parent.parent
    setup_py_content = (root / 'setup.py').read_text()
    for subpkg in (root / 'ai' / 'backend' / 'kernel').iterdir():
        if subpkg.is_dir() and subpkg.name != '__pycache__':
            rx = r"^\s+'ai\.backend\.kernel.{0}'".format(subpkg.name)
            m = re.search(rx, setup_py_content, re.M)
            if m is None:
                pytest.fail(f'Kernel subpackage "{subpkg.name}" '
                            'is not registered to setup.py!!')
