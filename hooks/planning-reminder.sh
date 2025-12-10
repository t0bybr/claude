#!/bin/bash
# Planning Reminder Hook - warns if PLANNING.md doesn't exist

# Parse JSON input
fp=$(jq -r '.tool_input.file_path // empty')

# Check if it's a project file (not .claude, node_modules, .git, /tmp)
if [[ "$fp" == *".claude"* ]] || [[ "$fp" == *"node_modules"* ]] || [[ "$fp" == *".git"* ]] || [[ "$fp" == *"/tmp"* ]]; then
  exit 0
fi

# Check if PLANNING.md exists
if [ ! -f "PLANNING.md" ]; then
  echo "💡 Consider creating PLANNING.md for project changes"
fi

exit 0
