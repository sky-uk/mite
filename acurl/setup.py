from setuptools import setup
from setuptools.extension import Extension


cpy_extension = Extension(
    '_acurl',
    sources=[
        'src/acurl.c',
        'src/event-loop.c',
        'src/response.c',
        'src/session.c',
        'src/ae/ae.c',
        'src/ae/zmalloc.c',
    ],
    libraries=['curl'],
    # Uncomment for debugging (yes this sucks)
    # extra_compile_args=['-g3', '-fno-omit-frame-pointer', '-O0', "-DDEBUG"],
)


setup(setup_requires="setuptools_scm", ext_modules=[cpy_extension])
