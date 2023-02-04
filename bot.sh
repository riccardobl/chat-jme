#!/bin/bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib
export NLTK_DATA="$PWD/nltk"
python bot.py $@