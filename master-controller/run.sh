#!/bin/bash
cd "$(dirname "$0")"
uvicorn web.websocket:app --host 0.0.0.0 --port 8080 --reload
