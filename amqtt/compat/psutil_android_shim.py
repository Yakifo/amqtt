"""
psutil_android_shim.py

Drop-in replacement for the small slice of `psutil` that amqtt actually
uses:

    self._current_process = psutil.Process()
    cpu_usage = self._current_process.cpu_percent(interval=0)
    mem_info_usage = self._current_process.memory_full_info()
    mem_size = mem_info_usage.rss / (1024 ** 2)

Both calls are on the *current* process (no pid passed in), so we only
ever read /proc/self/*, which stays readable on non-rooted Android/Termux
even when /proc/<other_pid>/* is restricted. No C extension, no build
step, works anywhere /proc is mounted (i.e. any real Linux, including
Android's kernel).

Usage — install this BEFORE amqtt (or anything else) imports psutil:

    import sys
    import psutil_android_shim
    sys.modules["psutil"] = psutil_android_shim

    import amqtt.broker  # now transparently uses the shim

Only implements what amqtt needs: Process(), .cpu_percent(interval=0),
.memory_full_info().rss. Anything else you call on this fake `psutil`
will raise AttributeError -- extend as needed.
"""

import os
import time


class _MemInfo:
    """Minimal stand-in for psutil's pmem/pfullmem namedtuple. Only .rss is populated."""

    __slots__ = ("rss",)

    def __init__(self, rss_bytes):
        self.rss = rss_bytes

    def __repr__(self):
        return f"_MemInfo(rss={self.rss})"


class Process:
    """Minimal stand-in for psutil.Process, current-process only."""

    def __init__(self, pid=None):
        self.pid = pid if pid is not None else os.getpid()
        self._last_cpu_time = None
        self._last_wall_time = None
        try:
            self._clk_tck = os.sysconf("SC_CLK_TCK")
        except (ValueError, AttributeError, OSError):
            self._clk_tck = 100  # typical Linux default

    def _read_cpu_times(self):
        """Return (utime, stime) in seconds, read from /proc/<pid>/stat."""
        with open(f"/proc/{self.pid}/stat", "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        # comm field is in parens and may itself contain ')' or spaces,
        # so split from the *last* ')' rather than by naive whitespace split.
        rparen = raw.rfind(")")
        fields = raw[rparen + 2:].split()
        # fields[0] == state (field 3 overall); utime is field 14, stime field 15
        utime_ticks = int(fields[11])
        stime_ticks = int(fields[12])
        return (utime_ticks / self._clk_tck, stime_ticks / self._clk_tck)

    def cpu_percent(self, interval=0):
        """
        Mirrors psutil's non-blocking usage pattern (interval=0 / None):
        compares CPU time consumed since the previous call against wall
        time elapsed since the previous call. First call returns 0.0,
        exactly like real psutil ("meaningless value ... supposed to
        ignore" per psutil's own docs).
        """
        if interval:
            time.sleep(interval)

        cpu_time = sum(self._read_cpu_times())
        now = time.monotonic()

        if self._last_cpu_time is None:
            self._last_cpu_time = cpu_time
            self._last_wall_time = now
            return 0.0

        elapsed_wall = now - self._last_wall_time
        elapsed_cpu = cpu_time - self._last_cpu_time

        self._last_cpu_time = cpu_time
        self._last_wall_time = now

        if elapsed_wall <= 0:
            return 0.0

        return (elapsed_cpu / elapsed_wall) * 100.0

    def memory_full_info(self):
        """
        Returns an object with a .rss attribute in bytes, read from
        /proc/<pid>/status (VmRSS). Real psutil's memory_full_info()
        also exposes uss/pss/etc via /proc/<pid>/smaps, which amqtt
        doesn't use and which is more likely to be permission-restricted
        on Android -- so we deliberately don't touch smaps here.
        """
        rss_kb = 0
        with open(f"/proc/{self.pid}/status", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # format: "VmRSS:\t   12345 kB"
                    rss_kb = int(line.split()[1])
                    break
        return _MemInfo(rss_bytes=rss_kb * 1024)


def cpu_count(logical=True):
    """Bonus helper in case anything else needs it -- cheap to support."""
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1

	print(cpu_count())
