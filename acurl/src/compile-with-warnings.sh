#!/bin/sh

INCLUDES="-I/usr/include/python3.8m"

CLANG_COMMAND="clang -O2 -Weverything -Wno-disabled-macro-expansion -Wno-padded -Wno-reserved-id-macro $INCLUDES -c"

GCC_COMMAND="gcc -O2 -Wall -Wextra -Wpedantic $INCLUDES -c"

if [ $# -eq 2 ]; then
    if [ $1 = clang ]; then
        $CLANG_COMMAND $2
    elif [ $1 = gcc ]; then
        $GCC_COMMAND $2
    else
        echo "Unknown compiler $1"
        exit 1
    fi
    exit 0
fi

$GCC_COMMAND $1
