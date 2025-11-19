#!/bin/bash


echo "##### Run tests with hatch #####"
# Sort of an hack we are using hatch to run the unit tests here. 
# For this reason we have to move back to the parent directory first.
hatch run test.py3.11:acurl-test ; TESTS_EXIT_CODE=$?
[ "$TESTS_EXIT_CODE" -eq 0 ] || exit 1
echo "##### Tests passed #####"
