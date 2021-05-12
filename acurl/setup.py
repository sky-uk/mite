from setuptools import setup
from setuptools.extension import Extension
import uvloop.loop
import os

cpy_extension = Extension(
    '_acurl',
    sources=[
        'src/acurl.c',
        'src/curl-wrapper.c',
        'src/response.c',
        'src/session.c',
    ],
    libraries=['curl', 'uv'],
    # extra_objects=[uvloop.loop.__file__],
    # Uncomment for debugging (yes this sucks)
    extra_compile_args=['-g3', '-fno-omit-frame-pointer', '-O0', "-DDEBUG"],
)


setup(
    ext_modules=[cpy_extension],
    setup_requires=["setuptools_scm", "cython"],
    use_scm_version={'root': '..', 'relative_to': __file__},
)
