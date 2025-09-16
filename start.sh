#!/bin/bash

# Activate the uv virtual environment
source .venv/bin/activate

# Run the MCP server (now with explicit host binding like TypeScript version)
python server.py
