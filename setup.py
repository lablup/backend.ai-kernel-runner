from setuptools import setup
from pathlib import Path
import re


def read_src_version():
    p = (Path(__file__).parent / 'ai' / 'backend' / 'kernel' / '__init__.py')
    src = p.read_text()
    m = re.search(r"^__version__\s*=\s*'([^']+)'", src, re.M)
    return m.group(1)


requires = [
    'async_timeout~=3.0',
    'pyzmq~=17.0',
    'uvloop~=0.10.0',
    'attrs>=18.0',  # to avoid pip 10 resolver issue
    'namedlist',
    'janus>=0.3.0',
    'msgpack~=0.5.6',
]
build_requires = [
    'wheel>=0.31.0',
    'twine>=1.11.0',
]
test_requires = [
    'pytest~=3.6.0',
    'pytest-asyncio>=0.8.0',
    'pytest-cov',
    'pytest-mock',
    'asynctest',
    'flake8',
    'codecov',
]
dev_requires = build_requires + test_requires + [
    'pytest-sugar>=0.9.1',
]
ci_requires = []


setup(
    name='backend.ai-kernel-runner',
    version=read_src_version(),
    description='User code executors for Backend.AI kernels',
    long_description=Path('README.rst').read_text(),
    url='https://github.com/lablup/backend.ai-kernel-runner',
    author='Lablup Inc.',
    author_email='joongi@lablup.com',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: No Input/Output (Daemon)',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development',
    ],
    packages=[
        'ai.backend.kernel',
        'ai.backend.kernel.python',
        'ai.backend.kernel.python.display',
        'ai.backend.kernel.python.drawing',
        'ai.backend.kernel.python.matplotlib',
        'ai.backend.kernel.c',
        'ai.backend.kernel.cpp',
        'ai.backend.kernel.golang',
        'ai.backend.kernel.rust',
        'ai.backend.kernel.java',
        'ai.backend.kernel.haskell',
        'ai.backend.kernel.julia',
        'ai.backend.kernel.lua',
        'ai.backend.kernel.nodejs',
        'ai.backend.kernel.octave',
        'ai.backend.kernel.php',
        'ai.backend.kernel.r',
        'ai.backend.kernel.r_server_ms',
        'ai.backend.kernel.git',
        'ai.backend.kernel.vendor',
        'ai.backend.kernel.vendor.aws_polly',
    ],
    python_requires='>=3.6',
    install_requires=requires,
    extras_require={
        'build': build_requires,
        'test': test_requires,
        'dev': dev_requires,
        'ci': ci_requires,
        # kernel-specific requirements
        'python': [
            'six', 'IPython', 'pandas', 'numpy',
            'matplotlib', 'msgpack-python'],
        'c': [],
        'cpp': [],
        'git': [],
        'golang': [],
        'rust': [],
        'java': [],
        'nodejs': [],
        'haskell': [],
        'php': [],
        'lua': [],
        'julia': [],
        'r': [],
        'r_server_ms': [
            'aiohttp', 'yarl',
        ],
        'octave': [],
        'vendor.aws_polly': ['boto3~=1.6.23', 'botocore~=1.9.23'],
    },
)
