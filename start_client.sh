#!/bin/sh

export PYTHONPATH="utility:share:rpc:../pb2:$PYTHONPATH" # 影响sys.path

python foo_bar_client/main.py
