import os, psutil
import gc
import itertools
import time
import sys
import msgpack

import matplotlib.pyplot as plt


class Meminfo:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()
    
    def write_msg(self, msg):
        msg_file = os.path.join(f"meminfo_{self.start_time}.msgpack")
        open(msg_file, "ab").write(
            msgpack.packb(msg, use_bin_type=True)
        )

    def stats(self):
        rss_mb = self.process.memory_info().rss / 1024 / 1024

        (count_0, count_1, count_2) = gc.get_count()
        (count_0_stats, count_1_stats, count_2_stats) = gc.get_stats()
        (count_0_collections, count_1_collections, count_2_collections) = (count_0_stats["collections"], count_1_stats["collections"], count_2_stats["collections"])

        stats = {
            "rss_mb": rss_mb,
            "count_0": count_0,
            "count_1": count_1,
            "count_2": count_2,
            "count_0_collections": count_0_collections,
            "count_1_collections": count_1_collections,
            "count_2_collections": count_2_collections,
            "time": time.time() - self.start_time
        }

        self.write_msg(stats)

    def read_stats(self, filename=None):
        if filename is None:
            filename = f"meminfo_{self.start_time}.msgpack"

        stats = {
            "rss_mb": [],
            "count_0": [],
            "count_1": [],
            "count_2": [],
            "count_0_collections": [],
            "count_1_collections": [],
            "count_2_collections": [],
            "time": []
        }

        with open(filename, "rb") as file_in:
            unpacker = msgpack.Unpacker(
                file_in, use_list=False, raw=False, strict_map_key=False
            )
            for row, (key, value) in itertools.product(unpacker, stats.items()):
                value.append(row[key])

        stats["filename"] = filename
        return stats

    def plot_graph(self, stats):
        fig, (mem_ax, gc_ax, gcc_ax) = plt.subplots(3, gridspec_kw={"height_ratios": [3, 1, 1]})
        fig.suptitle("Memory Usage vs. GC Count")

        mem_ax.set_title("Memory Usage")
        gc_ax.set_title("Garbage Collection Count")
        gcc_ax.set_title("Garbage Collection Collections Count")

        mem_ax.plot(stats["time"], stats["rss_mb"])
        mem_ax.set_xlabel("Time (s)")
        mem_ax.set_ylabel("Usage (MB)")
        mem_ax.grid()

        gc_ax.plot(stats["time"], stats["count_0"], label="count_0")
        gc_ax.plot(stats["time"], stats["count_1"], label="count_1")
        gc_ax.plot(stats["time"], stats["count_2"], label="count_2")
        gc_ax.set_xlabel("Time (s)")
        gc_ax.grid()
        gc_ax.legend()

        gcc_ax.plot(stats["time"], stats["count_0_collections"], label="count_0_collections")
        gcc_ax.plot(stats["time"], stats["count_1_collections"], label="count_1_collections")
        gcc_ax.plot(stats["time"], stats["count_2_collections"], label="count_2_collections")
        gcc_ax.set_xlabel("Time (s)")
        gcc_ax.grid()
        gcc_ax.legend()

        png_filename = stats["filename"].replace(".msgpack", ".png")

        # plt.show()
        fig.tight_layout()
        fig.set_size_inches(10, 10)
        plt.savefig(png_filename, format="png", dpi=300, bbox_inches="tight", pad_inches=0.1, )


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    meminfo = Meminfo()

    if filename is None:
        for _ in range(10):
            meminfo.stats()
            time.sleep(.1)

    stats = meminfo.read_stats(filename)
    meminfo.plot_graph(stats)
