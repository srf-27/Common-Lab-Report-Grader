#!/usr/bin/env python3
"""
Experiment Report Grader - Application Entry Point

Usage:
    python run.py [--host HOST] [--port PORT] [--debug]
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to Python path
SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

from src.experiment_report_grader.app import app


def main():
    parser = argparse.ArgumentParser(description="Experiment Report Grader")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"Starting Experiment Report Grader on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
