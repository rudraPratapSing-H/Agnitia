#!/usr/bin/env python3
"""Convenience runner for backend/scenarios/validate.py"""
import sys
from pathlib import Path

# Add backend/scenarios to sys.path
scenarios_dir = Path(__file__).resolve().parent.parent / "backend" / "scenarios"
sys.path.insert(0, str(scenarios_dir))

from validate import main

if __name__ == "__main__":
    main()
