import re

WAKE_KEYS = {"exit", "match", "silence"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_wake(wake_on):
    if wake_on is None:
        return {"exit": True, "match": None, "silence": None}
    if not isinstance(wake_on, dict) or not set(wake_on) <= WAKE_KEYS:
        raise ValueError("wake_on")
    exit_flag = wake_on.get("exit", False)
    if not isinstance(exit_flag, bool):
        raise ValueError("wake_on")
    match = wake_on.get("match")
    if match is not None:
        if not isinstance(match, str):
            raise ValueError("match")
        try:
            match = re.compile(match)
        except re.error:
            raise ValueError("match")
    silence = wake_on.get("silence")
    if silence is not None and (not _number(silence) or silence <= 0):
        raise ValueError("silence")
    return {"exit": exit_flag, "match": match, "silence": silence}


class Jobs:
    def __init__(self, spawn, clock, max_jobs=4, keep_lines=200):
        self._spawn, self._clock = spawn, clock
        self._max, self._keep = max_jobs, keep_lines
        self._jobs, self._count = {}, 0

    def start(self, argv, wake_on=None):
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise ValueError("argv")
        wake = _check_wake(wake_on)
        if sum(1 for j in self._jobs.values() if j["state"] == "running") >= self._max:
            raise RuntimeError("too_many_jobs")
        self._count += 1
        job_id = f"J{self._count}"
        now = self._clock()
        self._jobs[job_id] = {"argv": list(argv), "proc": self._spawn(list(argv)), "wake": wake, "state": "running", "code": None,
                              "lines": [], "pending": "", "last": now, "silent": False}
        return job_id

    def _job(self, job_id):
        if job_id not in self._jobs:
            raise ValueError("unknown_job")
        return self._jobs[job_id]

    def _take(self, job, text, final):
        parts = (job["pending"] + text).split("\n")
        job["pending"] = parts.pop()
        if final and job["pending"]:
            parts.append(job["pending"])
            job["pending"] = ""
        job["lines"] = (job["lines"] + parts)[-self._keep:]
        return parts

    def poll(self):
        events = []
        for job_id, job in self._jobs.items():
            if job["state"] != "running":
                continue
            proc, now = job["proc"], self._clock()
            text = proc.read()
            code = proc.poll()
            if code is not None:
                text += proc.read()
            new = self._take(job, text, code is not None)
            if new:
                job["last"], job["silent"] = now, False
            wake = job["wake"]
            if wake["match"] is not None:
                hit = next((line for line in new if wake["match"].search(line)), None)
                if hit is not None:
                    events.append({"job": job_id, "reason": "match", "detail": hit})
            if code is not None:
                job["state"], job["code"] = "exited", code
                if wake["exit"]:
                    events.append({"job": job_id, "reason": "exit", "detail": code})
            elif wake["silence"] is not None and not job["silent"] and now - job["last"] >= wake["silence"]:
                job["silent"] = True
                events.append({"job": job_id, "reason": "silence", "detail": now - job["last"]})
        return events

    def log(self, job_id, tail=20):
        job = self._job(job_id)
        if type(tail) is not int or tail < 1:
            raise ValueError("tail")
        return "\n".join(job["lines"][-tail:])

    def status(self, job_id):
        job = self._job(job_id)
        return {"job": job_id, "argv": list(job["argv"]), "state": job["state"], "code": job["code"], "lines": len(job["lines"])}

    def stop(self, job_id):
        job = self._job(job_id)
        if job["state"] != "running":
            return job["code"]
        proc = job["proc"]
        proc.terminate()
        try:
            code = proc.wait(timeout=5)
        except Exception:
            proc.kill()
            code = proc.wait(timeout=5)
        job["state"], job["code"] = "stopped", code
        return code

    def stop_all(self):
        running = [job_id for job_id, job in self._jobs.items() if job["state"] == "running"]
        for job_id in running:
            self.stop(job_id)
        return running
