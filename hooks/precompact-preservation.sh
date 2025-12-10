#!/bin/bash
# PreCompact Hook - sichert wichtigen State vor Context-Kompression

# Extrahiere transcript_path aus stdin
transcript_path=$(jq -r '.transcript_path // empty')

if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  # Suche nach TODOs, PLANNING-Referenzen, in_progress tasks
  grep -E "(TODO|PLANNING|in_progress|pending)" "$transcript_path" 2>/dev/null > /tmp/claude-precompact-state.txt

  # Speichere auch die letzten 50 Zeilen des Transcripts
  tail -n 50 "$transcript_path" > /tmp/claude-precompact-last50.txt 2>/dev/null

  echo "💾 Context state preserved in /tmp/claude-precompact-*.txt"
fi

exit 0
