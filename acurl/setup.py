import os

from Cython.Build import cythonize
from Cython.Compiler.Options import get_directive_defaults
from setuptools import Extension, setup

# https://stackoverflow.com/a/28301932/463500
if "IS_TOX_BUILD" in os.environ:
    directive_defaults = get_directive_defaults()
    directive_defaults["linetrace"] = True
    # directive_defaults['binding'] = True
    kwargs = {"define_macros": [("CYTHON_TRACE", "1")]}
else:
    kwargs = {}

extensions = [Extension("acurl", ["src/acurl.pyx"], libraries=["curl"], **kwargs)]

setup(
    ext_modules=cythonize(
        extensions,
        gdb_debug=True,
        compiler_directives={
            "warn.undeclared": True,
            "warn.unreachable": True,
            "warn.maybe_uninitialized": True,
            "warn.unused": True,
            "warn.unused_arg": True,
            "warn.unused_result": True,
        },
    ),
    setup_requires=["cython"],
)
