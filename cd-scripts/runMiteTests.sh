#!/bin/bash


echo "##### Run tests with hatch #####"
hatch run test.py3.11:test ; TESTS_EXIT_CODE=$?
[ "$TESTS_EXIT_CODE" -eq 0 ] || exit 1
echo "##### Tests passed #####"
