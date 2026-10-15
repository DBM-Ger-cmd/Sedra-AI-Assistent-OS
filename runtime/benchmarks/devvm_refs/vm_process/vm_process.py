import threading

LIMIT = 20000


class VmProcess:
    def __init__(self, run, argv):
        self._lock = threading.Lock()
        self._code = None
        self._abandoned = None
        self._out = ""
        self._ended = False
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._work, args=(run, list(argv)), daemon=True)
        self._thread.start()

    def _work(self, run, argv):
        try:
            result = run(argv) or {}
            status = result.get("status")
            out = result.get("output") or ""
            if not out and status != "completed":
                out = "[" + str(status) + "]\n"
            code = 0 if status == "completed" else 1
        except Exception as exc:
            out, code = type(exc).__name__ + ": " + str(exc) + "\n", 1
        with self._lock:
            if self._abandoned is None:
                self._out, self._code = out[-LIMIT:], code
            self._ended = True
        self._wake.set()

    def read(self):
        with self._lock:
            if self._abandoned is not None or not self._ended:
                return ""
            out, self._out = self._out, ""
            return out

    def poll(self):
        with self._lock:
            if self._abandoned is not None:
                return self._abandoned
            return self._code if self._ended else None

    def _abandon(self, code):
        with self._lock:
            if self._ended and self._abandoned is None:
                return
            self._abandoned = code
        self._wake.set()

    def terminate(self):
        with self._lock:
            if self._abandoned is None and not self._ended:
                self._abandoned = -15
        self._wake.set()

    def kill(self):
        self._abandon(-9)

    def wait(self, timeout=None):
        if self.poll() is None:
            self._wake.wait(timeout)
        if self.poll() is None:
            raise TimeoutError("still running")
        return self.poll()

    def running(self):
        return self._thread.is_alive()


def make_spawn(run, max_running=2):
    live = []

    def spawn(argv):
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise ValueError("argv")
        live[:] = [p for p in live if p.running()]
        if len(live) >= max_running:
            raise RuntimeError("too_many_processes")
        process = VmProcess(run, argv)
        live.append(process)
        return process

    return spawn
