"""
Binary-chunk version of the cluster sort, set up to run locally.

Workers read 5,000-int binary chunks from the shared mount and bubble-sort them;
the master merges sorted files pairwise as they arrive. The sort/merge logic is
the same as on the Orange Pi cluster. Only the environment-specific values
(worker IPs, NFS mount path, chunk sizes) are read from environment
variables so the same code runs on a laptop against simulated nodes:

  CLUSTER_NODES   comma-separated worker IPs   (default: the 4 Orange Pis)
  SHARED_DIR      shared "NFS" directory       (default: /mnt/usb1)
  MASTER_HOST     IP the master binds to       (default: auto)
  DISPY_PORT      dispy port                   (default: 9700)
  LINE_LIMIT      how many numbers to sort     (default: 100000)
  LINES_PER_CHUNK numbers per job              (default: 5000)
"""
import os
import array
import dispy
import time

SHARED = os.environ.get('SHARED_DIR', '/mnt/usb1')
def nodeSortJob(chunk_bin_file):
    """
    Reads a binary chunk file (array.array 'i' format),
    sorts it with bubble sort, writes a sorted binary chunk file.
    Returns (hostname, count, sorted_file_path) metadata only.
    """
    import array
    import os
    import socket
    def bubblesort(lst):
        n = len(lst)
        for i in range(n):
            for j in range(n - 1 - i):
                if lst[j] > lst[j + 1]:
                    lst[j], lst[j + 1] = lst[j + 1], lst[j]
        return lst
    file_size = os.path.getsize(chunk_bin_file)
    num_ints = file_size // 4
    int_array = array.array('i')
    with open(chunk_bin_file, 'rb') as f:
        int_array.fromfile(f, num_ints)
    lst = bubblesort(int_array.tolist())
    out_file = chunk_bin_file.replace('.bin', '.sorted.bin')
    out_arr = array.array('i', lst)
    with open(out_file, 'wb') as f:
        out_arr.tofile(f)
    return (os.environ.get('NODE_NAME') or socket.gethostname(), len(lst), out_file)
def merge_two_binary_files(file1, file2, out_filepath, final=False):
    CHUNK = 10000

    def read_int(f):
        buf = f.read(4)
        if len(buf) < 4:
            return None
        a = array.array('i')
        a.frombytes(buf)
        return a[0]

    out_buf = array.array('i')
    out_f = open(out_filepath, 'w', encoding='utf-8') if final else open(out_filepath, 'wb')

    def flush():
        nonlocal out_buf
        if final:
            for n in out_buf:
                out_f.write(f"{n}\n")
        else:
            out_buf.tofile(out_f)
        out_buf = array.array('i')

    try:
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            val1 = read_int(f1)
            val2 = read_int(f2)

            while val1 is not None and val2 is not None:
                if val1 <= val2:
                    out_buf.append(val1)
                    val1 = read_int(f1)
                else:
                    out_buf.append(val2)
                    val2 = read_int(f2)
                if len(out_buf) >= CHUNK:
                    flush()

            while val1 is not None:
                out_buf.append(val1)
                val1 = read_int(f1)
                if len(out_buf) >= CHUNK:
                    flush()

            while val2 is not None:
                out_buf.append(val2)
                val2 = read_int(f2)
                if len(out_buf) >= CHUNK:
                    flush()

            if out_buf:
                flush()
    finally:
        out_f.close()


if __name__ == '__main__':
    start_time = time.time()

    nodes = os.environ.get('CLUSTER_NODES', '192.168.0.10,192.168.0.20,192.168.0.30,192.168.0.40').split(',')
    cluster = dispy.JobCluster(
        nodeSortJob,
        nodes=nodes,
        host=os.environ.get('MASTER_HOST'),
        dispy_port=int(os.environ.get('DISPY_PORT', 9700)),
        ping_interval=900,
        loglevel=30,  # warnings only, keeps the terminal output readable
    )

    ascii_filepath = f"{SHARED}/data1.set"
    final_file     = f"{SHARED}/sorted_output.txt"

    LINES_PER_CHUNK = int(os.environ.get('LINES_PER_CHUNK', 5000))
    LINE_LIMIT      = int(os.environ.get('LINE_LIMIT', 100000))   # sort 100K numbers total

    jobs         = []
    pending_jobs = []
    ready_files  = []
    total_lines  = 0
    merge_count  = 0
    chunk_index  = 0
    lines_read   = 0

    print(f"[MASTER] Binary sort pipeline starting on {len(nodes)} node(s): {', '.join(nodes)}")
    print(f"[MASTER] Input : {ascii_filepath}")
    print(f"[MASTER] Output: {final_file}")
    print(f"[MASTER] Chunk size: {LINES_PER_CHUNK} ints | Limit: {LINE_LIMIT} lines")
    print()
    buffer = []
    with open(ascii_filepath, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            buffer.append(int(stripped))
            lines_read += 1

            if len(buffer) >= LINES_PER_CHUNK:
                chunk_file = f"{SHARED}/chunk_{chunk_index}.bin"
                a = array.array('i', buffer)
                with open(chunk_file, 'wb') as bf:
                    a.tofile(bf)

                job = cluster.submit(chunk_file)
                job.id = chunk_index
                jobs.append(job)
                pending_jobs.append(job)
                print(f"[MASTER] Chunk {chunk_index:>3}: {len(buffer)} ints → {chunk_file}  [job submitted]")

                buffer = []
                chunk_index += 1

            if lines_read >= LINE_LIMIT:
                break
    if buffer:
        chunk_file = f"{SHARED}/chunk_{chunk_index}.bin"
        a = array.array('i', buffer)
        with open(chunk_file, 'wb') as bf:
            a.tofile(bf)
        job = cluster.submit(chunk_file)
        job.id = chunk_index
        jobs.append(job)
        pending_jobs.append(job)
        print(f"[MASTER] Chunk {chunk_index:>3}: {len(buffer)} ints → {chunk_file}  [job submitted]")

    print(f"\n[MASTER] All {len(jobs)} jobs submitted ({lines_read} lines). Waiting for results...\n")
    while pending_jobs or len(ready_files) > 1:
        for job in pending_jobs[:]:
            if job.status in [dispy.DispyJob.Finished, dispy.DispyJob.Terminated]:
                pending_jobs.remove(job)
                if job.result:
                    host, count, sorted_file = job.result
                    ready_files.append(sorted_file)
                    total_lines += count
                    print(f"[MASTER] Job {job.id:>3} done on {host} ({count} ints) | ready files: {len(ready_files)}")
                else:
                    print(f"[MASTER] Job {job.id:>3} FAILED: {job.exception}")
        if len(ready_files) >= 2:
            file1 = ready_files.pop(0)
            file2 = ready_files.pop(0)
            merge_count += 1

            is_final = (not pending_jobs) and (len(ready_files) == 0)

            if is_final:
                out_file = final_file
                print(f"[MASTER] FINAL merge #{merge_count}: {os.path.basename(file1)} + {os.path.basename(file2)} → sorted_output.txt (ASCII)")
            else:
                out_file = f"{SHARED}/merged_tmp_{merge_count}.bin"
                print(f"[MASTER] Binary merge #{merge_count}: {os.path.basename(file1)} + {os.path.basename(file2)} → {os.path.basename(out_file)}")

            merge_two_binary_files(file1, file2, out_file, final=is_final)

            if os.path.exists(file1): os.remove(file1)
            if os.path.exists(file2): os.remove(file2)

            ready_files.append(out_file)
        else:
            time.sleep(0.5)
    if len(ready_files) == 1 and ready_files[0] != final_file:
        remaining = ready_files[0]
        file_size = os.path.getsize(remaining)
        a = array.array('i')
        with open(remaining, 'rb') as f:
            a.fromfile(f, file_size // 4)
        with open(final_file, 'w', encoding='utf-8') as f:
            for n in a:
                f.write(f"{n}\n")
        os.remove(remaining)

    cluster.print_status()
    cluster.close()

    elapsed = time.time() - start_time
    print(f"\n[MASTER] Sort complete!")
    print(f"[MASTER] Total integers sorted: {total_lines}")
    print(f"[MASTER] Output file: {final_file}")
    print(f"[MASTER] Total time: {elapsed:.2f}s")
    print(f"\nVerify with:")
    print(f"  head -{lines_read} {ascii_filepath} | sort -n | diff - {final_file}")
