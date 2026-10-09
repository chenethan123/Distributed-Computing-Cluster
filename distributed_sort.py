import os
import dispy
import time


def nodeSortJob(start_byte, end_byte, filepath):
    import os
    import socket

    def bubblesort(numbers):
        for a in range(len(numbers)):
            for b in range(len(numbers) - 1):
                if numbers[b] > numbers[b + 1]:
                    numbers[b], numbers[b + 1] = numbers[b + 1], numbers[b]
        return numbers

    def getlist(start, end, file_path):
        numbers = []
        # Byte offsets are interpreted in binary mode to avoid text seek ambiguity.
        with open(file_path, "rb") as f:
            if start > 0:
                f.seek(start - 1)
                if f.read(1) != b"\n":
                    f.readline()
            else:
                f.seek(0)

            while f.tell() < end:
                line = f.readline()
                if not line:
                    break
                numbers.append(int(line.strip()))
        return numbers

    numbers = bubblesort(getlist(start_byte, end_byte, filepath))
    out_filepath = "/mnt/usb1/data_" + str(start_byte) + ".sorted"
    with open(out_filepath, "w") as f:
        for number in numbers:
            f.write(str(number) + "\n")
    return socket.gethostname(), len(numbers), out_filepath


def merge_two_files(file1, file2, out_filepath):
    """Merge two sorted text files incrementally."""
    with open(file1, "r") as f1, open(file2, "r") as f2, open(out_filepath, "w") as out:
        line1 = f1.readline()
        line2 = f2.readline()

        while line1 and line2:
            val1 = int(line1.strip())
            val2 = int(line2.strip())
            if val1 <= val2:
                out.write(f"{val1}\n")
                line1 = f1.readline()
            else:
                out.write(f"{val2}\n")
                line2 = f2.readline()

        while line1:
            out.write(line1)
            line1 = f1.readline()
        while line2:
            out.write(line2)
            line2 = f2.readline()


if __name__ == "__main__":
    start_time = time.time()
    filepath = "/mnt/usb1/data1.set"
    final_file = "/mnt/usb1/outfile.txt"
    chunk_size_bytes = 50000
    limit_in_bytes = 90000000

    cluster = dispy.JobCluster(
        nodeSortJob,
        nodes=["192.168.0.10", "192.168.0.20", "192.168.0.30", "192.168.0.40"],
        ping_interval=900,
    )

    try:
        actual_file_size = os.path.getsize(filepath)
        file_size = min(actual_file_size, limit_in_bytes)
        jobs = []
        startindex = 0
        print(f"Targeting {file_size} bytes (approx {file_size / (1024 * 1024):.2f} MiB)...")

        while startindex < file_size:
            endindex = min(startindex + chunk_size_bytes, file_size)
            job = cluster.submit(startindex, endindex, filepath)
            if job is None:
                raise RuntimeError(f"Could not submit chunk starting at byte {startindex}")
            job.id = startindex
            jobs.append(job)
            startindex = endindex

        print(f"Submitted {len(jobs)} jobs.")
        pending_jobs = list(jobs)
        ready_files = []
        total_lines = 0
        merge_count = 0

        if not jobs:
            open(final_file, "w").close()

        while pending_jobs or len(ready_files) > 1:
            for job in pending_jobs[:]:
                if job.status in [dispy.DispyJob.Finished, dispy.DispyJob.Terminated]:
                    pending_jobs.remove(job)
                    if job.status == dispy.DispyJob.Finished and job.result:
                        host, count, chunk_file = job.result
                        ready_files.append(chunk_file)
                        total_lines += count
                        print(f"Job {job.id} finished on {host} with {count} lines.")
                    else:
                        raise RuntimeError(f"Job {job.id} failed; aborting to avoid an incomplete output.")

            if len(ready_files) >= 2:
                file1 = ready_files.pop(0)
                file2 = ready_files.pop(0)
                merge_count += 1
                is_final_merge = not pending_jobs and not ready_files
                out_file = final_file if is_final_merge else f"/mnt/usb1/merged_tmp_{merge_count}.txt"
                print(f"Merging: {file1} and {file2} -> {out_file}")
                merge_two_files(file1, file2, out_file)
                if os.path.exists(file1):
                    os.remove(file1)
                if os.path.exists(file2):
                    os.remove(file2)
                ready_files.append(out_file)
            else:
                time.sleep(0.5)

        if len(ready_files) == 1 and ready_files[0] != final_file:
            os.replace(ready_files[0], final_file)

        print("\n--- JOB COMPLETE ---")
        print(f"Total lines processed: {total_lines}")
        print(f"Total time taken: {time.time() - start_time:.2f} seconds")
        cluster.print_status()
    finally:
        cluster.close()
