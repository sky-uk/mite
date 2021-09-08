Command for running valgrind from within this directory:

```
PYTHONMALLOC=malloc valgrind --tool=memcheck --suppressions=valgrind-python.supp \
    --leak-check=full --show-leak-kinds=all -- \
    python leak_check.py |& tee malloc.out
```

Make sure you do `pip install -e ../acurl` after making code changes as
these will not automatically be compiled/picked up.

The valgrind-python.supp file comes from the python repo:
<https://svn.python.org/projects/python/trunk/Misc/valgrind-python.supp>
