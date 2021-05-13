from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("acurl", ["src/acurl.pyx"], libraries=["curl"])
]

setup(
    ext_modules=cythonize(extensions, gdb_debug=True, compiler_directives={
        "warn.undeclared": True,
        "warn.unreachable": True,
        "warn.maybe_uninitialized": True,
        "warn.unused": True,
        "warn.unused_arg": True,
        "warn.unused_result": True,
    }),
    setup_requires=["setuptools_scm", "cython"],
    use_scm_version={'root': '..', 'relative_to': __file__},
)
