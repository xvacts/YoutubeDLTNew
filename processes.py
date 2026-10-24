"""Launch external tools without the frozen GUI's DLL environment; stop their tree."""
import contextlib
import os
import signal
import subprocess
import sys
import threading

from engine import process_options

_spawn_lock = threading.Lock()


def start_process(arguments, **kwargs):
    with _spawn_lock:
        reset = os.name == 'nt' and getattr(sys, 'frozen', False)
        if reset:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            return subprocess.Popen(arguments, **process_options(), **kwargs)
        finally:
            if reset:
                ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)


class ProcessTree:
    def __init__(self, process):
        self.process = process
        self.job = None
        if os.name == 'nt':
            self._attach_windows_job()

    def _attach_windows_job(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IOCounters),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) \
                or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(self.process._handle))):
            if handle:
                kernel.CloseHandle(handle)
            self.process.kill()
            self.process.wait()
            raise OSError('Cannot safely manage the yt-dlp process tree')
        self.kernel = kernel
        self.job = handle

    def stop(self):
        if self.job:
            self.kernel.TerminateJobObject(self.job, 1)
        elif os.name != 'nt':
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGTERM)
        elif self.process.poll() is None:
            self.process.kill()

    def close(self):
        if self.process.poll() is None or os.name != 'nt':
            self.stop()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.process.pid, signal.SIGKILL)
            else:
                self.process.kill()
            self.process.wait(timeout=5)
        finally:
            if self.job:
                self.kernel.CloseHandle(self.job)
                self.job = None
