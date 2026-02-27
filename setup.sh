#!/bin/bash
# Turret Simulator — Setup
echo "Installing dependencies..."
pip install panda3d flask flask-cors websockets numpy
echo ""
echo "Done! To continue development with Claude Code:"
echo "  cd turret_sim"
echo "  claude"
echo ""
echo "Claude Code will read CLAUDE.md automatically and pick up from where we left off."
echo "Next step: Panda3D 3D renderer + visual effects"
