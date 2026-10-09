#!/bin/bash
# Opens two Terminal windows side by side and runs the single-node and
# 4-node cluster sorts at the same time, each followed by the sort check.
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/cluster.sh" start || exit 1
[ -f "$DIR/shared/data1.set" ] || "$DIR/.venv/bin/python" "$DIR/generate_data.py"

osascript <<OSA
tell application "Finder" to set b to bounds of window of desktop
set W to item 3 of b
set H to item 4 of b
tell application "Terminal"
  activate
  set winL to do script "cd " & quoted form of "$DIR" & " && ./run.sh single"
  set bounds of front window to {0, 25, W / 2, H}
  set winR to do script "cd " & quoted form of "$DIR" & " && ./run.sh cluster"
  set bounds of front window to {W / 2, 25, W, H}
end tell
OSA
