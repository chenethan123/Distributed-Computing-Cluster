#!/bin/bash
# Run the distributed sort, then verify the output.
#   ./run.sh cluster   master on 127.0.0.1 -> 4 worker nodes
#   ./run.sh single    master on 127.0.0.1 -> 1 standalone node
cd "$(dirname "$0")"
MODE=${1:-cluster}
N=${LINE_LIMIT:-100000}
BOLD=$'\e[1m'; DIM=$'\e[2m'; GREEN=$'\e[32m'; RED=$'\e[31m'; CYAN=$'\e[36m'; RESET=$'\e[0m'

if [ "$MODE" = cluster ]; then
  export CLUSTER_NODES=127.0.0.10,127.0.0.20,127.0.0.30,127.0.0.40 DISPY_PORT=9700
  TITLE="4-NODE CLUSTER"
else
  export CLUSTER_NODES=127.0.0.1 DISPY_PORT=9800
  TITLE="SINGLE NODE (no cluster)"
fi
SHARED="$PWD/shared/$MODE"
export MASTER_HOST=127.0.0.1 LINE_LIMIT=$N

# Fresh shared "NFS" directory with the same input file for both modes
[ -f shared/data1.set ] || .venv/bin/python generate_data.py "$N" >/dev/null
rm -rf "$SHARED" && mkdir -p "$SHARED"
ln -s "$PWD/shared/data1.set" "$SHARED/data1.set"
# Short absolute "mount point" that every node sees at the same path, like NFS /mnt/usb1
MOUNT=/tmp/usb1-$MODE
ln -sfn "$SHARED" "$MOUNT"

clear
echo "${BOLD}${CYAN}━━━ $TITLE ━━━${RESET}"
echo "${DIM}\$ python cluster_sort.py${RESET}"
(cd "$SHARED" && SHARED_DIR=$MOUNT "$OLDPWD/.venv/bin/python" -u "$OLDPWD/cluster_sort.py") 2>&1 \
  | grep -v -e "fault recovery" -e "dispy client at" -e "pycos - version" -e "dispy client version"

OUT="$SHARED/sorted_output.txt"
echo
echo "${BOLD}━━━ VERIFY ━━━${RESET}"
echo "${DIM}\$ sort -n -c sorted_output.txt   ${RESET}${DIM}# exits 0 only if every line is in order${RESET}"
if sort -n -c "$OUT"; then echo "${GREEN}✓ sorted_output.txt is in ascending order${RESET}"; else echo "${RED}✗ not sorted${RESET}"; fi
echo "${DIM}\$ head -$N data1.set | sort -n | diff - sorted_output.txt${RESET}"
if head -"$N" shared/data1.set | sort -n | diff -q - "$OUT" >/dev/null; then
  echo "${GREEN}✓ VERIFIED: identical to sort -n ($(wc -l < "$OUT" | tr -d ' ') numbers, no differences)${RESET}"
else
  echo "${RED}✗ MISMATCH${RESET}"
fi
