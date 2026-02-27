#!/usr/bin/env python3
"""
Turret Simulator - Entry Point
Run this to start the game.
"""

import sys
import os

# Add project root to path so canonical module imports work
# (e.g. "from game.manager import GameManager")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import main

if __name__ == "__main__":
    main()
