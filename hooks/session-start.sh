#!/bin/bash
# Session Start Hook - zeigt Projekt-Kontext an

echo "=== Claude Session Start ==="

# Check für PLANNING.md
if [ -f "PLANNING.md" ]; then
  echo "📋 PLANNING.md found - project in progress"
fi

# Check für DOCUMENTATION.md
if [ -f "DOCUMENTATION.md" ]; then
  echo "📚 DOCUMENTATION.md available"
fi

# Git Info
if [ -d ".git" ]; then
  branch=$(git branch --show-current 2>/dev/null)
  if [ -n "$branch" ]; then
    echo "🌿 Current branch: $branch"
  fi

  # Uncommitted changes?
  if ! git diff-index --quiet HEAD 2>/dev/null; then
    echo "⚠️  Uncommitted changes present"
  fi
fi

# Check für README
if [ -f "README.md" ]; then
  echo "📖 README.md available"
fi

echo "=============================="
exit 0
