# Distributed Computing Cluster

A five-node ARM-based distributed computing cluster using Linux, Python, Ethernet, and shared NFS storage. A master node schedules distributed sorting jobs across four worker nodes and merges the resulting sorted files.

## Architecture

- **One master node** submits jobs through the Python `dispy` library and performs the final merges.
- **Four ARM worker nodes** sort integer chunks independently.
- **NFS shared storage** makes `/mnt/usb1` and the input/output files accessible at the same path on every node.
- **Prometheus and Grafana** were used as monitoring tools installed and configured on the machines, independent of the sorting script. Monitoring configuration and dashboards are not included in this repo.

## How the distributed sort works

1. The master divides the input file into byte ranges (50,000 bytes each by default).
2. `dispy` dispatches each range to a worker.
3. Workers read whole newline-delimited integers, bubble-sort their assigned numbers, and write sorted chunks to the NFS mount.
4. The master incrementally merges sorted output files and deletes temporary files.
5. The merged result is written to `/mnt/usb1/outfile.txt` and the script reports lines processed and total elapsed time.

The sorting phase is distributed, but the merge phase runs on the master. Bubble sort is O(n²) per chunk and is not intended as a production-optimal sorting algorithm.

## Project files

- `distributed_sort.py`: worker job function, job scheduling, and sorted-file merging
- `requirements.txt`: Python dependency (`dispy`)
- `.gitignore`: excludes generated data and local Python artifacts

## Setup and execution

1. Connect the master and four worker machines via Ethernet and mount the same NFS share at `/mnt/usb1` on every machine.
2. Install a compatible Python version and `dispy` on the machines; run `dispynode` on each worker, following your installed version's instructions.
3. Replace the four example worker IP addresses in `distributed_sort.py` with your workers' actual addresses.
4. Put input at `/mnt/usb1/data1.set`, with **one integer per line**. Ensure workers can read/write the shared directory.
5. On the master, run:

```bash
python -m pip install -r requirements.txt
python distributed_sort.py
```

The script uses a 90,000,000-byte input cap and 50,000-byte job chunks. Output and temporary file paths are hardcoded; don't run multiple instances on the same share at once. If a worker job fails, processing aborts instead of silently producing an incomplete output.

## Performance and monitoring

The project's resume reports sorting approximately **5 million integers** with **3.5× speedup** relative to single-node execution, and a further **40% runtime reduction** following cluster profiling and workload batching. These are user-reported project results, not independently reproduced benchmarks from the checked-in code. Raw benchmark measurements and Prometheus/Grafana dashboards have not been provided.

Grafana is a separate dashboard service and does **not** need to be imported in Python. In this deployment, monitoring ran on the Orange Pi machines rather than inside `distributed_sort.py`.

## Limitations

- Designed for a specific local cluster environment, not a plug-and-play cloud deployment.
- Shared NFS mount and remote worker services must already be configured.
- Sequential merging on the master can become a bottleneck.
- Byte-range input assumes newline-delimited integer records.
