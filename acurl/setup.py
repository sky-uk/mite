import os
from setuptools import setup
from setuptools.extension import Extension


with open(os.path.join('acurl', 'version.py')) as f:
    # FIXME: code smell
    exec(f.read())


# Building without nanoconfig
cpy_extension = Extension('_acurl',
                          sources=['src/acurl.c',
                                   'src/event-loop.c',
                                   'src/response.c',
                                   'src/session.c',
                                   'src/ae/ae.c',
                                   'src/ae/zmalloc.c'
                                   ],
                          libraries=['curl'],
                          # Uncomment for debugging (yes this sucks)
                          # extra_compile_args=['-g3', '-fno-omit-frame-pointer', '-O0', "-DDEBUG"],
                          )


setup(
    version=__version__,
    ext_modules=[cpy_extension],
    test_suite="tests",
)
