"""The model scheduler (Spec 2, D2.1): ONE owner of the model server and the GPU lease, slots of the running server per run.

Two levels. The load lease `gpu` (testlab.db, `TestLab.try_acquire`) is held by this object while its server runs; nobody else in SEDRA
starts a model. Slot leases (`slot_leases`, schema 2 of testlab.db) let a run send requests to that server; they never allow loading,
stopping or changing a recipe. Who waits, who gets a slot and why not is decided by the pure `slotplan` inside `slot_store.take`.

It knows neither missions nor gates (the Guard decides what a run may do), never starts or stops a process by name (only through its
own loader and runtime), and never switches to the cloud. Off unless config/model_scheduler.yaml or the machine overlay sets `enabled: true`
(unlocked by the Captain, OP-S2-18); off means behaviour as today (the supervisor reserves per job, uix_server holds its own lease).
"""
from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager

from . import slot_store, vramplan
from .model_scheduler_config import ModelSchedulerConfig  # noqa: F401  (re-exported: callers import it from here)
from .model_scheduler_decisions import DecisionMixin
from .model_scheduler_handover import HandoverMixin
from .slotplan import decide_reason
from .testlab import SCHEMA_VERSION, utc_text

OWNER = "sedra-scheduler"
DEFAULT_VRAM_RESERVE_GB = 0.7          # resource_scheduler.vram_reserve_gb; used only when no resource scheduler is attached


class SchedulerError(Exception):
    """A refused or failed scheduler step. `code` is a reason the supervisor already knows (`provider_unavailable`,
    `hardware_pressure`); `reason` says what exactly (`gpu_lease_busy:<owner>:<purpose>`, `vram_insufficient`, `model_swap_not_allowed`)."""

    def __init__(self, reason, *, code="provider_unavailable", detail=None):
        super().__init__(reason)
        self.code, self.reason, self.detail = code, reason, detail




# --------------------------------------------------------------------------- the scheduler

class ModelScheduler(HandoverMixin, DecisionMixin):
    def __init__(self, config, lab, *, loader=None, runtime=None, resources=None, audit=None, profile=None, owner=OWNER,
                 lease_ttl_s=600, beat_every_s=30):
        """`lab` TestLab (schema 2), `loader` ModelLoader (starts the server with the recipe's slots), `runtime` LlamaServerRuntime (status,
        pid), `resources` ResourceScheduler (measured free VRAM, the one reservation of the server), `profile()` the active hardware profile id."""
        if lab.schema < SCHEMA_VERSION:
            raise ValueError(lab.schema_error or "testlab_schema_too_old")
        self.config, self.lab, self.loader, self.runtime, self.resources = config, lab, loader, runtime, resources
        self.audit, self._profile, self.owner = audit, profile, owner
        self.lease_ttl_s, self.beat_every_s = lease_ttl_s, beat_every_s
        self._lock = threading.RLock()
        self._token = None                 # the load lease while the server runs
        self._beat_stop = None
        self._resolution = None            # what the running server was started with
        self._reserved = None              # job id of the server's reservation in the resource scheduler
        self._direct = set()               # direct calls of this process that may still ask (reap keeps them)
        self._drain_since = None
        self._drain_overdue = False
        self._init_decisions()

    @property
    def enabled(self):
        return self.config.enabled

    def _require(self):
        if not self.config.enabled:
            raise SchedulerError("model_scheduler_disabled")

    def _now(self):
        return utc_text(self.lab.clock())

    @contextmanager
    def _conn(self):
        conn = self.lab.connect()
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _server(conn):
        row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
        return dict(row) if row else {"name": "main", "gen": 0, "recipe": None, "slots": None, "context_per_slot": None, "state": "aus",
                                      "pid": None, "since": None, "restarts": "[]", "garbage": "[]", "reason": None, "owner": None}

    @staticmethod
    def _active(conn, but=None):
        return [dict(r) for r in conn.execute("SELECT * FROM slot_leases WHERE state = 'aktiv'") if r["run_id"] != but]

    def _audit(self, event, **payload):
        if self.audit:
            self.audit.append(event, component="model-scheduler", payload=payload)

    def _cap(self):
        """The slot limit of the active hardware profile (G2-S2-06), or None: the recipe decides."""
        if self._profile is None:
            return None
        try:
            return self.config.slots_cap_by_profile.get(self._profile())
        except Exception:
            return None

    # ---- slot leases
    def take_for_job(self, job_id, priority, *, recipe=None, agent_id=None, task_id=None, owner="job-supervisor", enqueued=None):
        """Enter a job in the queue (once) and try to give it a slot. {granted, slot, reason}; a refused job stays waiting. `enqueued`
        (UTC text) is when the job joined the supervisor's queue, so ageing and arrival order are the same in both places."""
        self._require()
        now = self._now()
        with self._conn() as conn:
            row = conn.execute("SELECT state, slot FROM slot_leases WHERE run_id = ?", (job_id,)).fetchone()
            if row is not None and row["state"] == "aktiv":
                return {"granted": True, "slot": row["slot"], "reason": None}
            slot_store.request(conn, job_id, "job", owner, priority, enqueued or now, agent_id=agent_id, task_id=task_id, ttl_s=self.config.slot_ttl_s)
            return slot_store.take(conn, job_id, now, self.config.plan(), recipe)

    def wait_for_job(self, job_id, priority, *, agent_id=None, task_id=None, owner="job-supervisor", enqueued=None):
        """Put a job (back) in the queue without trying it now; an active lease of it goes back to waiting (start refused before it ran)."""
        self._require()
        now = self._now()
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("UPDATE slot_leases SET state = 'wartend', slot = NULL, server_gen = NULL, started = NULL, heartbeat = NULL "
                             "WHERE run_id = ? AND state = 'aktiv'", (job_id,))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return slot_store.request(conn, job_id, "job", owner, priority, enqueued or now, agent_id=agent_id, task_id=task_id, ttl_s=self.config.slot_ttl_s)

    def release(self, run_id, outcome="fertig"):
        self._require()
        with self._conn() as conn:
            return slot_store.release(conn, run_id, outcome, self._now())

    def beat(self, run_id):
        self._require()
        with self._conn() as conn:
            return slot_store.beat(conn, run_id, self._now())

    def reap(self, live_run_ids):
        """Leases of runs that cannot ask any more end (`verfallen`). `live_run_ids`: every job that still waits or runs; the direct
        calls of this process are added here. The clock alone never frees a place."""
        self._require()
        with self._conn() as conn:
            return slot_store.reap(conn, sorted(set(live_run_ids) | self._direct), self._now())

    @contextmanager
    def slot(self, owner, priority, *, wait_s=0, poll_s=0.5, sleep=time.sleep, agent_id=None):
        """A slot for one direct call (chat, desk) around the model request: `with scheduler.slot("chat", 7, wait_s=30): ...`. Waiting
        longer than `wait_s` raises `slot_wait_timeout` with the reason, never a silent wait. The server must already run."""
        self._require()
        run_id = f"direkt-{uuid.uuid4().hex[:12]}"
        deadline = self.lab.clock() + wait_s
        with self._conn() as conn:
            slot_store.request(conn, run_id, "direkt", owner, priority, self._now(), agent_id=agent_id, ttl_s=self.config.slot_ttl_s)
        self._direct.add(run_id)
        try:
            while True:
                with self._conn() as conn:
                    out = slot_store.take(conn, run_id, self._now(), self.config.plan())
                    state = self._server(conn)["state"]
                if out["granted"]:
                    if state != "bereit":
                        raise SchedulerError("server_aus")           # a direct call cannot start the server: it has no recipe
                    break
                if self.lab.clock() >= deadline:
                    raise SchedulerError("slot_wait_timeout", detail={"grund": out["reason"]})
                sleep(poll_s)
            yield {"run_id": run_id, "slot": out["slot"]}
        finally:
            with self._conn() as conn:
                slot_store.release(conn, run_id, "fertig", self._now())
            self._direct.discard(run_id)

    # ---- the server
    def ensure_server(self, resolution, *, run_id=None, owner=None):
        """Make the server run with this resolution's recipe. Reuse when it already does; start it when it is off (the caller holds the
        starter's slot); refuse with the scheduler's reason otherwise. Returns {action, gen, slots, load}. `owner` (e.g. `werkstatt`) only
        names the caller in the audit: the server and the load lease stay the scheduler's."""
        self._require()
        recipe = resolution.get("capability_id")
        with self._lock:
            with self._conn() as conn:
                server = self._server(conn)
                others = self._active(conn, but=run_id)
            if server["state"] == "bereit":
                if not self._alive():
                    self._server_gone()
                    raise SchedulerError("server_exited")
                if server["recipe"] == recipe:
                    return {"action": "reused", "gen": server["gen"], "slots": server["slots"],
                            "load": {"identifier": resolution.get("model"), "context_length": server["context_per_slot"], "action": "reused"}}
                reason = decide_reason(server, recipe, "normal", others, self.config.plan())
                if reason is not None or self.config.swap != "idle":
                    # `fallback` lets a job use the running fallback recipe; switching the attempt to it is not built yet (open point).
                    raise SchedulerError(reason or "model_swap_fallback_unsupported")
                self._shutdown("aus", reason="swap")                     # rule `idle`: nobody else is active, reload
                if run_id is not None:                                   # the stop interrupted the asking run's own slot: it keeps it
                    with self._conn() as conn:
                        conn.execute("UPDATE slot_leases SET state = 'aktiv', reason = NULL WHERE run_id = ? AND state = 'unterbrochen'", (run_id,))
            elif server["state"] != "aus":
                mode = server["state"] if server["state"] in ("drain", "exklusiv") else "normal"
                raise SchedulerError(decide_reason(server, recipe, mode, others, self.config.plan()) or server["state"])
            return self._start(resolution, run_id, owner)

    def _alive(self):
        if self.runtime is None:
            return True                       # nothing to ask; the request itself will fail if the server is gone
        try:
            return bool(self.runtime.status().get("running"))
        except Exception:
            return False

    def _memory(self, resolution, slots):
        """Weights once, KV per slot (SCH-03). (need, None) or (need, denial with need_gb / measured_free_gb / limit_gb)."""
        est = resolution.get("estimated_resources") or {}
        kv = float(est.get("kv_cache_gb") or 0.0)
        on_cpu = est.get("kv_cache_placement") == "cpu"
        need = vramplan.server_need(float(est.get("vram_gb") or 0.0), 0.0 if on_cpu else kv / slots, slots,
                                    ram_gb=float(est.get("ram_gb") or 0.0) + (kv if on_cpu else 0.0))
        reserve = self.resources.config.vram_reserve_gb if self.resources is not None else DEFAULT_VRAM_RESERVE_GB
        free = self.resources.measured_free_vram_gb() if self.resources is not None and self.resources.enabled else None
        denial = vramplan.fits(need["vram_gb"], self.config.vram_limit_gb, reserve, self.config.vram_limit_gb if free is None else free)
        if denial is not None and free is None:
            denial["measured_free_gb"] = None
        return need, denial

    def _start(self, resolution, run_id, owner=None):
        recipe, window = resolution.get("capability_id"), resolution.get("context_window")
        slots = int(resolution.get("slots") or 1)
        cap = self._cap()
        admitted = min(slots, cap) if cap else slots      # the server runs as measured; the profile only limits the leases
        if self.loader is None or not getattr(self.loader, "enabled", True):
            raise SchedulerError("model_loader_unavailable")
        need, denial = self._memory(resolution, slots)
        if denial is not None:
            values = {k: denial[k] for k in ("need_gb", "measured_free_gb", "limit_gb", "reserve_gb")}
            if self.resources is not None:
                self.resources.audit_denied(f"server:{recipe}", "vram_insufficient", **values, limit_reason=denial["reason"])
            else:
                self._audit("RESOURCE_DENIED", job_id=f"server:{recipe}", reason="vram_insufficient", **values, limit_reason=denial["reason"])
            raise SchedulerError("vram_insufficient", code="hardware_pressure", detail=denial)
        self._take_gpu(recipe)
        started = False
        try:
            with self._conn() as conn:
                server = slot_store.set_server(conn, self._now(), "startet", recipe=recipe, slots=admitted, context_per_slot=window,
                                               pid=None, owner=None, reason=None)
                started = True
                if run_id is not None:            # the starter took its slot while the server was off: it belongs to the new generation
                    conn.execute("UPDATE slot_leases SET server_gen = ? WHERE run_id = ? AND state = 'aktiv'", (server["gen"], run_id))
            if self.resources is not None and self.resources.enabled:
                grant = self.resources.reserve(f"server:{recipe}", f"gen-{server['gen']}",
                                               {**(resolution.get("estimated_resources") or {}), "vram_gb": need["vram_gb"], "ram_gb": need["ram_gb"],
                                                "kv_cache_gb": 0.0})
                if grant["status"] == "DENIED":
                    raise SchedulerError(grant["reason"], code="hardware_pressure", detail=grant.get("detail"))
                self._reserved = f"server:{recipe}"
            try:
                load = self.loader.ensure(dict(resolution))
            except Exception as exc:
                raise SchedulerError(getattr(exc, "reason", None) or str(exc) or type(exc).__name__,
                                     code=getattr(exc, "code", "provider_unavailable")) from exc
            pid = None
            if self.runtime is not None:
                try:
                    pid = self.runtime.status().get("pid")
                except Exception:
                    pid = None
            with self._conn() as conn:
                server = slot_store.set_server(conn, self._now(), "bereit", pid=pid)
            self._resolution = dict(resolution)
            self._audit("SLOT_SERVER_STARTED", recipe=recipe, gen=server["gen"], slots=slots, admitted=admitted,
                        context_per_slot=window, vram_gb=need["vram_gb"], pid=pid, asked_by=owner)
            return {"action": "started", "gen": server["gen"], "slots": admitted, "load": load}
        except BaseException as exc:
            self._audit("SLOT_SERVER_START_FAILED", recipe=recipe, reason=str(getattr(exc, "reason", None) or exc)[:200])
            self._free_reservation()
            if started:
                with self._conn() as conn:
                    slot_store.set_server(conn, self._now(), "aus", owner=None, reason="start_failed")
            self._release_gpu()
            raise

    def _take_gpu(self, recipe):
        if self._token is not None:
            return
        purpose = f"Modellserver {recipe}"
        token = self.lab.try_acquire(self.owner, purpose, ttl_s=self.lease_ttl_s)
        if token is None:
            blocker = next((r for r in self.lab.reservations() if r["priority"] > 0 and r["owner"] != self.owner), None)
            if blocker is not None:
                raise SchedulerError(f"gpu_lease_deferred:{blocker['owner']}")        # the night chain comes first (D2.7, point 5)
            holder = self.lab.holder() or {"owner": "?", "purpose": "?"}
            raise SchedulerError(f"gpu_lease_busy:{holder['owner']}:{holder['purpose']}")
        self._token = token
        stop = threading.Event()
        self._beat_stop = stop

        def beat():
            while not stop.wait(self.beat_every_s):
                if not self.lab.heartbeat(token):          # taken over: we do not own the GPU any more
                    self._lease_lost(token)
                    return
        threading.Thread(target=beat, name="model-scheduler-lease", daemon=True).start()

    def _lease_lost(self, token):
        """Somebody took the load lease over (we were silent too long). The server may still run, but it is no longer ours to hand out:
        it is marked `gesperrt` (no new slots, active leases end `unterbrochen`), and the Captain decides; nothing is stopped by name."""
        if self._token != token:
            return
        self._token = None
        with self._conn() as conn:
            server = slot_store.set_server(conn, self._now(), "gesperrt", reason="gpu_lease_lost")
        holder = self.lab.holder() or {}
        self._audit("SLOT_GPU_LEASE_LOST", recipe=server["recipe"], gen=server["gen"], holder=holder.get("owner"), interrupted=server["interrupted"])

    def _release_gpu(self):
        if self._beat_stop is not None:
            self._beat_stop.set()
            self._beat_stop = None
        if self._token is not None:
            self.lab.release(self._token)
            self._token = None

    def _free_reservation(self):
        if self._reserved is not None and self.resources is not None:
            try:
                self.resources.release_job(self._reserved)
            except Exception as exc:
                self._audit("SLOT_RESERVATION_RELEASE_FAILED", error=type(exc).__name__)
        self._reserved = None

    def _shutdown(self, state, *, owner=None, reason=None):
        """Stop the own server (own loader, own pid), give back its reservation and the load lease, set `state`. Active leases end
        `unterbrochen` when `state` is `aus` or `gesperrt`."""
        if self._resolution is not None and self.loader is not None:
            try:
                self.loader.unload(self._resolution)
            except Exception as exc:
                self._audit("SLOT_SERVER_STOP_FAILED", error=type(exc).__name__)
        self._free_reservation()
        with self._conn() as conn:
            server = slot_store.set_server(conn, self._now(), state, recipe=None, slots=None, context_per_slot=None, pid=None,
                                           owner=owner, reason=reason)
        recipe = (self._resolution or {}).get("capability_id")
        self._resolution = None
        self._release_gpu()
        self._audit("SLOT_SERVER_STOPPED", recipe=recipe, state=state, reason=reason, interrupted=server["interrupted"])
        return server

    def _server_gone(self, reason="server_exited"):
        """The server ended (crash) or is stopped as suspect (`reason` garbage). Count the restart; past `restart.max` in the window the server
        is locked (D2.8) and the Captain is asked (`decisions`). It is started again lazily by the next run, never here. The canary runs again."""
        with self._conn() as conn:
            count = slot_store.note(conn, "restarts", self._now(), self.config.restart_window_s)
        state = "gesperrt" if count > self.config.restart_max else "aus"
        server = self._shutdown(state, reason=reason)
        self._invalidate_canary(f"scheduler: {reason}")
        self._audit("SLOT_SERVER_EXITED", restarts=count, state=state, interrupted=server["interrupted"])
        if state == "gesperrt":
            self._audit("SLOT_SERVER_GESPERRT", restarts=count, window_s=self.config.restart_window_s)
        return state

    # ---- views
    def view(self):
        """The shape of Spec 4 D4.2.4 plus server, exklusiv, warnung. Never raises."""
        if not self.config.enabled:
            return {"enabled": False, "error": None}
        try:
            now = self._now()
            with self._conn() as conn:
                out = slot_store.view(conn, now, self.config.plan())
                server = self._server(conn)
                pending = slot_store.handover_pending(conn, now)
                enqueued = {r["run_id"]: r["enqueued"] for r in conn.execute("SELECT run_id, enqueued FROM slot_leases WHERE state = 'wartend'")}
        except Exception as exc:
            return {"enabled": True, "error": type(exc).__name__}
        warn = out.get("warnung")
        out["warnung"] = {"art": warn["grund"], "run_id": warn["run_id"], "seit": enqueued.get(warn["run_id"])} if warn else None
        exclusive = None
        if server["state"] in ("drain", "exklusiv") and (server["reason"] or "").startswith("exklusiv:"):
            req = next((p for p in pending if p["owner"] == server["owner"]), None)
            exclusive = {"eigner": server["owner"], "zweck": req["purpose"] if req else None, "seit": req["since"] if req else server["since"]}
        out.update(enabled=True, error=None, modell=server["recipe"], warte_max_s=self.config.wait_max_s, exklusiv=exclusive,
                   lease=self._token is not None, slots_cap=self._cap(), standard_slots=dict(self.config.standard_slots))
        return out

    def events(self, limit=20):
        with self._conn() as conn:
            return slot_store.events(conn, limit)
