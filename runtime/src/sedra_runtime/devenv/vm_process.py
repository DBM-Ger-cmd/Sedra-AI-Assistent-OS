import threading


class VmProcess:
    def __init__(self, run, argv):
        self._run = run
        self._argv = list(argv)
        self._exit_code = None
        self._output = None
        self._abandoned = False
        self._abandon_code = None
        self._finished = False
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        try:
            result = self._run(list(self._argv))
            status = result.get("status", "")
            output = result.get("output", "")
            if output is None:
                output = ""
            if status != "completed":
                self._exit_code = 1
            else:
                self._exit_code = 0
            if len(output) > 20000:
                output = output[-20000:]
            if output == "" and status != "completed":
                output = "[" + status + "]\n"
            with self._lock:
                self._output = output
                self._finished = True
            self._done_event.set()
            self._wake.set()
        except Exception as e:
            with self._lock:
                self._exit_code = 1
                output = type(e).__name__ + ": " + str(e) + "\n"
                self._output = output
                self._finished = True
            self._done_event.set()
            self._wake.set()

    def read(self):
        with self._lock:
            if self._abandoned or not self._finished:
                return ""
            out = self._output
            self._output = None
            return out if out is not None else ""

    def poll(self):
        with self._lock:
            if self._abandoned:
                return self._abandon_code
            if not self._finished:
                return None
            return self._exit_code

    def terminate(self):
        with self._lock:
            if self._abandoned:
                return
            if self._finished:
                return
            self._abandoned = True
            self._abandon_code = -15
        self._wake.set()

    def kill(self):
        with self._lock:
            if self._finished and not self._abandoned:
                return
            self._abandoned = True
            self._abandon_code = -9
        self._wake.set()

    def wait(self, timeout=None):
        with self._lock:
            if self._abandoned or self._finished:
                code = self._abandon_code if self._abandoned else self._exit_code
                return code
        if not self._wake.wait(timeout=timeout):
            raise TimeoutError()
        with self._lock:
            if self._abandoned:
                return self._abandon_code
            if self._finished:
                return self._exit_code
            raise TimeoutError()


def make_spawn(run, max_running=2):
    class _Spawner:
        def __init__(self):
            self._count = 0
            self._lock = threading.Lock()
            self._not_full = threading.Condition(self._lock)

        def spawn(self, argv):
            if not isinstance(argv, list) or len(argv) == 0 or not all(isinstance(a, str) for a in argv):
                raise ValueError("argv")
            with self._not_full:
                if self._count >= max_running:
                    raise RuntimeError("too_many_processes")
                self._count += 1
            def tracked(argv):
                try:
                    return run(argv)
                finally:
                    with self._not_full:
                        self._count -= 1
                        self._not_full.notify()
            try:
                proc = VmProcess(tracked, argv)
            except BaseException:
                with self._not_full:
                    self._count -= 1
                    self._not_full.notify()
                raise
            return proc

    spawner = _Spawner()
    return spawner.spawn
