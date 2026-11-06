import re


class Jobs:
    def __init__(self, spawn, clock, max_jobs=4, keep_lines=200):
        self._spawn = spawn
        self._clock = clock
        self._max_jobs = max_jobs
        self._keep_lines = keep_lines
        self._jobs = {}
        self._next_id = 1
        self._running_order = []
        self._outputs = {}
        self._pending = {}

    def _validate_wake_on(self, wake_on):
        if wake_on is None:
            return {"exit": True}
        if not isinstance(wake_on, dict):
            raise ValueError("wake_on")
        allowed_keys = {"exit", "match", "silence"}
        for k in wake_on:
            if k not in allowed_keys:
                raise ValueError("wake_on")
        result = {}
        if "exit" in wake_on:
            v = wake_on["exit"]
            if not isinstance(v, bool):
                raise ValueError("wake_on")
            result["exit"] = v
        if "match" in wake_on:
            v = wake_on["match"]
            if v is not None:
                if not isinstance(v, str):
                    raise ValueError("match")
                try:
                    re.compile(v)
                except re.error:
                    raise ValueError("match")
            result["match"] = v
        if "silence" in wake_on:
            v = wake_on["silence"]
            if v is not None:
                if isinstance(v, bool):
                    raise ValueError("silence")
                if not isinstance(v, (int, float)):
                    raise ValueError("silence")
                if v <= 0:
                    raise ValueError("silence")
            result["silence"] = v
        return result

    def _validate_argv(self, argv):
        if not isinstance(argv, list) or len(argv) == 0 or not all(isinstance(a, str) for a in argv):
            raise ValueError("argv")

    def start(self, argv, wake_on=None):
        self._validate_argv(argv)
        wake_on = self._validate_wake_on(wake_on)
        running_count = sum(1 for j in self._jobs.values() if j["state"] == "running")
        if running_count >= self._max_jobs:
            raise RuntimeError("too_many_jobs")
        argv_copy = list(argv)
        proc = self._spawn(list(argv_copy))
        job_id = "J" + str(self._next_id)
        self._next_id += 1
        self._jobs[job_id] = {
            "id": job_id,
            "argv": argv_copy,
            "state": "running",
            "code": None,
            "proc": proc,
            "wake_on": wake_on,
            "lines": 0,
            "last_output_time": self._clock(),
            "silence_fired": False,
        }
        self._outputs[job_id] = []
        self._running_order.append(job_id)
        return job_id

    def status(self, job_id):
        if job_id not in self._jobs:
            raise ValueError("unknown_job")
        j = self._jobs[job_id]
        return {
            "job": j["id"],
            "argv": list(j["argv"]),
            "state": j["state"],
            "code": j["code"],
            "lines": j["lines"],
        }

    def stop(self, job_id):
        if job_id not in self._jobs:
            raise ValueError("unknown_job")
        j = self._jobs[job_id]
        if j["state"] != "running":
            return j["code"]
        proc = j["proc"]
        proc.terminate()
        try:
            code = proc.wait(timeout=5)
        except Exception:
            proc.kill()
            code = proc.wait(timeout=5)
        j["state"] = "stopped"
        j["code"] = code
        if job_id in self._running_order:
            self._running_order.remove(job_id)
        return code

    def _add_lines(self, job_id, new_lines):
        if not new_lines:
            return
        self._outputs[job_id].extend(new_lines)
        kept = self._outputs[job_id][-self._keep_lines:]
        self._outputs[job_id] = kept
        self._jobs[job_id]["lines"] = len(kept)

    def _process_output(self, job_id, text, now, exited):
        if not text:
            return []
        prev = self._pending.get(job_id, "")
        if prev:
            text = prev + text
            prev = ""
        parts = text.split("\n")
        complete = parts[:-1]
        pending = parts[-1]
        new_lines = list(complete)
        if exited and pending:
            new_lines.append(pending)
            self._pending[job_id] = ""
        else:
            self._pending[job_id] = pending
        if new_lines:
            self._add_lines(job_id, new_lines)
            self._jobs[job_id]["last_output_time"] = now
            self._jobs[job_id]["silence_fired"] = False
        return new_lines

    def poll(self):
        events = []
        for job_id in list(self._running_order):
            j = self._jobs[job_id]
            if j["state"] != "running":
                continue
            now = self._clock()
            proc = j["proc"]
            text = proc.read()
            code = proc.poll()
            if code is not None:
                text += proc.read()
                j["state"] = "exited"
                j["code"] = code
                if job_id in self._running_order:
                    self._running_order.remove(job_id)
                exited = True
            else:
                exited = False
            if text:
                new_lines = self._process_output(job_id, text, now, exited)
                if j["wake_on"].get("match") is not None:
                    for line in new_lines:
                        m = re.search(j["wake_on"]["match"], line)
                        if m:
                            events.append({
                                "job": job_id,
                                "reason": "match",
                                "detail": line,
                            })
                            break
            if code is not None and j["wake_on"].get("exit") is True:
                events.append({
                    "job": job_id,
                    "reason": "exit",
                    "detail": code,
                })
            if code is None and j["wake_on"].get("silence") is not None:
                if not j["silence_fired"]:
                    elapsed = now - j["last_output_time"]
                    if elapsed >= j["wake_on"]["silence"]:
                        events.append({
                            "job": job_id,
                            "reason": "silence",
                            "detail": elapsed,
                        })
                        j["silence_fired"] = True
        return events

    def log(self, job_id, tail=20):
        if not isinstance(tail, int) or isinstance(tail, bool) or tail < 1:
            raise ValueError("tail")
        if job_id not in self._jobs:
            raise ValueError("unknown_job")
        lines = list(self._outputs[job_id])
        return "\n".join(lines[-tail:])

    def stop_all(self):
        ids = list(self._running_order)
        for jid in ids:
            self.stop(jid)
        return ids
