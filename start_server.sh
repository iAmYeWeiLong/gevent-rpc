#!/bin/sh

export PYTHONPATH="utility:share:rpc:../pb2:$PYTHONPATH" # 影响sys.path

python main_service/main.py
