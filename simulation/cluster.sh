#!/bin/bash
# Start/stop the simulated network.
#
#   cluster  4 worker nodes on 127.0.0.10/.20/.30/.40 (stand-ins for 192.168.0.10-.40)
#   single   1 standalone node on 127.0.0.1 (separate dispy port, for the baseline)
#
# Each node is a real dispynode process limited to 1 CPU, so a node behaves
# like one worker board instead of using the whole laptop.
cd "$(dirname "$0")"
PY=".venv/bin/python -u"
NODE=.venv/bin/dispynode.py
WORKERS=(10 20 30 40)

check_network() {
  local missing=()
  for i in "${WORKERS[@]}"; do
    ifconfig lo0 | grep -q "inet 127.0.0.$i " || missing+=("$i")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "Simulated network not set up. Add the worker IPs once (resets on reboot):"
    echo "  sudo sh -c 'for i in ${WORKERS[*]}; do ifconfig lo0 alias 127.0.0.\$i up; done'"
    exit 1
  fi
}

start() {
  check_network
  stop >/dev/null 2>&1
  mkdir -p logs
  for n in 1 2 3 4; do
    ip=127.0.0.${WORKERS[$((n-1))]}
    NODE_NAME=node$n nohup $PY $NODE -i $ip -c 1 --name node$n --dest_path_prefix "$PWD/nodes/node$n" --clean --daemon \
      > logs/node$n.log 2>&1 &
    echo "node$n  $ip  started (1 CPU)"
  done
  NODE_NAME=standalone nohup $PY $NODE -i 127.0.0.1 -p 9800 -c 1 --name standalone --dest_path_prefix "$PWD/nodes/standalone" --clean --daemon \
    > logs/standalone.log 2>&1 &
  echo "standalone  127.0.0.1:9800  started (1 CPU)"
  sleep 3
  status
}

stop() {
  pkill -f "dispynode.py -i 127.0.0" && echo "All nodes stopped." || echo "No nodes running."
}

status() {
  for f in logs/node*.log logs/standalone.log; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .log)
    if grep -q "serving" "$f" && pgrep -f -- "--name $name " >/dev/null; then
      echo "  ✓ $name  $(ps -o args= -p $(pgrep -f -- "--name $name " | head -1) | grep -oE '\-i [0-9.]+( -p [0-9]+)?' | cut -c4-)"
    else
      echo "  ✗ $name  not running (see $f)"
    fi
  done
}

case "$1" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Usage: ./cluster.sh start|stop|status" ;;
esac
