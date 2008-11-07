#!/bin/sh


for test in test/*.py; do
    echo ------------------------------------------------------
    echo $test
    echo

    python $test
done

