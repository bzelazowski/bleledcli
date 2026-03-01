#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")" && uv run main.py "$@"