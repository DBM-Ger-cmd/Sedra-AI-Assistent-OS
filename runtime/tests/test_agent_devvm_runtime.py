import json
import os
import sys
import subprocess
import tempfile
import unittest
import env_skip

from guppi_runtime.agent_manager import run_worker
from guppi_runtime.agent_manager.devvm_runtime import DevVmRuntime, RefusedStart

RUN = "run-0123456789ab"


class FakeProcess:
    pid = 4242


class DevVmRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = os.path.join(self.tmp.name, "runtime")
        self.project = os.path.join(self.tmp.name, "project")
        os.makedirs(os.path.join(self.runtime, "benchmarks", "devvm_specs"))
        open(os.path.join(self.runtime, "benchmarks", "devvm_specs", "am_demo.py"), "w").close()
        self.calls, self.alive_pids, self.owns = [], set(), True
        self.port = DevVmRuntime(self.runtime, self.project, python="py", popen=self.popen, alive=lambda pid: pid in self.alive_pids, owns=lambda pid, run_id: self.owns)
        self.run_dir = os.path.join(self.project, "runtime_data", "agent_manager", "runs", RUN)

    def popen(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return FakeProcess()

    def assignment(self, spec="am_demo"):
        return {"agent_ref": "guppi.devvm.coder@1.0.0", "mission_id": "M-1", "input_ref": spec}

    def write_done(self, text):
        with open(os.path.join(self.run_dir, "done.json"), "w") as handle:
            handle.write(text)

    def test_start_launches_one_detached_worker_and_records_the_request(self):
        self.port.start(RUN, self.assignment())
        cmd, kw = self.calls[0]
        self.assertEqual(cmd[:3], ["py", "-m", "guppi_runtime.agent_manager.run_worker"])
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        self.assertEqual(json.load(open(os.path.join(self.run_dir, "request.json")))["spec"], "am_demo")
        self.assertEqual(open(os.path.join(self.run_dir, "pid")).read(), "4242")
        self.assertEqual(kw["env"]["TESTLAB_OWNER"], "agent_manager:" + RUN)

    def test_only_a_spec_name_is_accepted(self):
        for bad in ("../../etc/passwd", "am_demo.py", "AM_DEMO", "nope_not_a_spec", "a b", "", None, 5, "am_demo; calc"):
            with self.assertRaises(RefusedStart, msg=repr(bad)):
                self.port.start(RUN, self.assignment(bad))
        self.assertEqual(self.calls, [])

    @env_skip.needs_dulwich
    def test_the_own_tests_of_the_model_are_run_and_reported_but_never_gate(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks"))
        import devvm_build
        calls = []

        class Ws:
            def __init__(self, tree):
                self.files = tree

            def tree(self):
                return self.files

        def vm(ws, commands, extra):
            calls.append(commands)
            return {"status": "completed" if len(calls) % 2 else "failed", "output": "x" * 500}

        self.assertEqual(devvm_build.own_tests(vm, Ws(["mod.py"])), {"present": False, "passed": None, "output": ""})
        self.assertEqual(calls, [])
        ok = devvm_build.own_tests(vm, Ws(["mod.py", "tests/test_mod.py"]))
        bad = devvm_build.own_tests(vm, Ws(["tests/test_mod.py"]))
        self.assertEqual((ok["present"], ok["passed"], len(ok["output"]), bad["passed"]), (True, True, 400, False))
        self.assertEqual(calls[0], [["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."]])

    def test_the_benchmark_scripts_the_worker_starts_compile(self):
        bench = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks")
        for name in ("devvm_build.py", "devvm_agents_bench.py", "moe_sweep.py", "cuda_crash_hunt.py", "model_compare.py", "qwen_build.py", "agent_tool_probe.py", "probes/qwen_probe.py", "probes/plan_probe.py", "probes/review_probe.py", "probes/checker_probe.py", "probes/stdbench_probe.py"):
            with open(os.path.join(bench, name), encoding="utf-8") as handle:
                compile(handle.read(), name, "exec")

    def test_a_probe_name_is_accepted_only_when_its_script_exists(self):
        os.makedirs(os.path.join(self.runtime, "benchmarks", "probes"))
        open(os.path.join(self.runtime, "benchmarks", "probes", "arbiter_probe.py"), "w").close()
        self.port.start(RUN, self.assignment("probe_arbiter"))
        for bad in ("probe_nothing", "probe_", "probe_arbiter_probe", "probe_../x"):
            with self.assertRaises(RefusedStart, msg=bad):
                self.port.start("run-aaaaaaaaaaaa", self.assignment(bad))
        self.assertEqual(len(self.calls), 1)

    def test_bad_run_id_and_reuse_are_refused(self):
        for bad in ("run-xyz", "../run-0123456789ab", None, "run-0123456789ABC"):
            with self.assertRaises(RefusedStart):
                self.port.start(bad, self.assignment())
        self.port.start(RUN, self.assignment())
        with self.assertRaises(RefusedStart):
            self.port.start(RUN, self.assignment())
        self.assertEqual(len(self.calls), 1)

    def test_inspect_follows_pid_and_done_file_and_never_guesses_failed(self):
        self.assertEqual(self.port.inspect(RUN), "unknown")
        self.port.start(RUN, self.assignment())
        self.assertEqual(self.port.inspect(RUN), "unknown")
        self.alive_pids.add(4242)
        self.assertEqual(self.port.inspect(RUN), "running")
        self.alive_pids.clear()
        self.assertEqual(self.port.inspect(RUN), "unknown")
        self.write_done('{"state": "succeeded"}')
        self.assertEqual(self.port.inspect(RUN), "succeeded")
        self.write_done('{"state": "failed"}')
        self.assertEqual(self.port.inspect(RUN), "failed")
        self.write_done("{broken")
        self.assertEqual(self.port.inspect(RUN), "unknown")
        self.assertEqual(self.port.inspect("../x"), "unknown")


class StopTest(DevVmRuntimeTest):
    def setUp(self):
        super().setUp()
        self.killed = []
        self.port = DevVmRuntime(self.runtime, self.project, python="py", popen=self.popen, alive=lambda pid: pid in self.alive_pids, kill_tree=self.killed.append, owns=lambda pid, run_id: self.owns)

    def test_a_pid_that_belongs_to_another_program_is_neither_running_nor_killed(self):
        self.port.start(RUN, self.assignment())
        self.alive_pids.add(4242)
        self.owns = False
        self.assertEqual(self.port.inspect(RUN), "unknown")
        self.assertFalse(self.port.stop(RUN, "reason"))
        self.assertEqual(self.killed, [])
        self.assertIn("belongs to another program", self.port.result(RUN)["reason"])

    def test_the_real_check_needs_the_run_worker_and_the_run_id_in_the_command_line(self):
        from guppi_runtime.agent_manager import devvm_runtime as module
        line = "py.exe -m guppi_runtime.agent_manager.run_worker C:/x/runs/" + RUN + " rt project"
        original = module.process_command_line
        try:
            for command, expected in ((line, True), ("notepad.exe", False), ("py.exe -m guppi_runtime.agent_manager.run_worker C:/x/runs/run-ffffffffffff", False), (None, False)):
                module.process_command_line = lambda pid, command=command: command
                self.assertIs(module.process_belongs_to(1, RUN), expected, command)
        finally:
            module.process_command_line = original

    def test_stop_kills_the_recorded_pid_tree_and_writes_the_outcome(self):
        self.port.start(RUN, self.assignment())
        self.alive_pids.add(4242)
        self.assertTrue(self.port.stop(RUN, "because"))
        self.assertEqual(self.killed, [4242])
        done = self.port.result(RUN)
        self.assertEqual((done["state"], done["stopped"], done["reason"]), ("failed", True, "because"))
        self.assertEqual(self.port.inspect(RUN), "failed")
        self.assertFalse(self.port.stop(RUN, "twice"))
        self.assertEqual(self.killed, [4242])

    def test_stop_of_a_vanished_worker_kills_nothing_but_records_the_outcome(self):
        self.port.start(RUN, self.assignment())
        self.assertFalse(self.port.stop(RUN, "gone"))
        self.assertEqual(self.killed, [])
        self.assertEqual(self.port.inspect(RUN), "failed")

    def test_stop_refuses_bad_ids_and_unknown_runs_are_left_alone(self):
        with self.assertRaises(RefusedStart):
            self.port.stop("../x", "r")
        self.assertFalse(self.port.stop(RUN, "never started"))
        self.assertEqual(self.port.inspect(RUN), "unknown")


class WorkerTest(unittest.TestCase):
    def worker_run(self, output, code, seed=False):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "run")
            os.makedirs(run_dir)
            with open(os.path.join(run_dir, "request.json"), "w") as handle:
                json.dump({"spec": "am_demo"}, handle)
            if seed:
                os.makedirs(os.path.join(tmp, "p", "runtime_data", "agent_manager", "seeds", "am_demo"))
            seen = []

            class Result:
                stdout, stderr, returncode = output, "", code

            def runner(cmd, **kw):
                seen.append(cmd)
                return Result()
            done = run_worker.run(run_dir, os.path.join(tmp, "r"), os.path.join(tmp, "p"), runner=runner, clock=iter([0, 7.5]).__next__)
            with open(os.path.join(run_dir, "done.json")) as handle:
                return done, seen[0], json.load(handle)

    def test_passed_hidden_test_means_succeeded(self):
        out = "x\nattempt 1: hidden test PASSED | own check accepted=False | 5 s -> cand_dir\n# run ended: done\n"
        done, cmd, stored = self.worker_run(out, 0)
        self.assertEqual((done["state"], done["hidden_passed"], done["candidate"], done["seconds"]), ("succeeded", True, "cand_dir", 7.5))
        self.assertEqual(done, stored)
        self.assertIn("--context", cmd)
        self.assertNotIn("--seed", cmd)

    def test_a_candidate_path_with_spaces_is_kept_whole(self):
        out = "attempt 1: hidden test FAILED | own check accepted=UNJUDGED | 8576.0 s, 23 agent runs -> <projekte>\\Guppy\\runtime data\\devvm_candidates\\am006\\attempt_01\n# run ended: done\n"
        done = self.worker_run(out, 0)[0]
        self.assertEqual((done["state"], done["hidden_passed"], done["candidate"]), ("failed", False, "<projekte>\\Guppy\\runtime data\\devvm_candidates\\am006\\attempt_01"))

    def test_failed_hidden_test_or_bad_exit_is_failed(self):
        self.assertEqual(self.worker_run("attempt 1: hidden test FAILED | x\n", 0)[0]["state"], "failed")
        self.assertEqual(self.worker_run("attempt 1: hidden test PASSED | x\n", 1)[0]["state"], "failed")

    def test_options_file_adds_only_known_switches_with_fixed_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            seeds = os.path.join(tmp, "runtime_data", "agent_manager", "seeds")
            os.makedirs(seeds)

            def cmd(payload):
                with open(os.path.join(seeds, "am_demo.options.json"), "w") as handle:
                    handle.write(payload if isinstance(payload, str) else json.dumps(payload))
                return run_worker.command("py", "rt", tmp, "am_demo")

            self.assertNotIn("--check-first", cmd({}))
            good = cmd({"check_first": True, "parallel_check": True, "tidy": True, "parallel": 2, "context": 24576, "arbiter": "coder.llama_gptoss", "checker": "coder.llama_gptoss", "coder": "jan"})
            for part in ("--check-first", "--parallel-check", "--tidy", "--parallel", "--arbiter", "--checker", "coder.llama_gptoss"):
                self.assertIn(part, good)
            self.assertEqual(good[good.index("--context") + 1], "24576")
            self.assertEqual(good[good.index("--coder") + 1], "jan")
            bad = cmd({"check_first": "yes", "parallel": 9, "context": 999999, "arbiter": "x; calc", "checker": "a b", "tidy": "yes", "coder": "../evil", "extra": "--seed C:/x", "parallel_check": 1})
            self.assertEqual(bad[bad.index("--context") + 1], "32768")
            self.assertEqual(bad[bad.index("--coder") + 1], "coder.local_primary")
            for part in ("--check-first", "--parallel-check", "--tidy", "--parallel", "--arbiter", "--checker", "--seed"):
                self.assertNotIn(part, bad)
            self.assertEqual(cmd({})[cmd({}).index("--rework") + 1], "2")
            self.assertNotIn("--hidden-feedback", cmd({}))
            tuned = cmd({"hidden_feedback": True, "rework": 3})
            self.assertIn("--hidden-feedback", tuned)
            self.assertEqual(tuned[tuned.index("--rework") + 1], "3")
            wrong = cmd({"hidden_feedback": "yes", "rework": 9})
            self.assertNotIn("--hidden-feedback", wrong)
            self.assertEqual(wrong[wrong.index("--rework") + 1], "2")
            solo = cmd({"all_models": "coder.llama_qwen3_coder"})
            self.assertEqual(solo[solo.index("--all-models") + 1], "coder.llama_qwen3_coder")
            self.assertNotIn("--all-models", cmd({"all_models": "x; calc"}))
            tuned = cmd({"sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "evil": 1, "presence_penalty": 99, "min_p": True}})
            self.assertEqual(json.loads(tuned[tuned.index("--sampling") + 1]), {"temperature": 0.7, "top_p": 0.8, "top_k": 20})
            self.assertNotIn("--sampling", cmd({"sampling": {"top_k": 999}}))
            solo_cmd = cmd({"mode": "solo"})
            self.assertEqual(solo_cmd[solo_cmd.index("--mode") + 1], "solo")
            self.assertNotIn("--mode", cmd({"mode": "evil; calc"}))
            think = cmd({"reasoning": "off", "reasoning_budget": 512})
            self.assertEqual((think[think.index("--reasoning") + 1], think[think.index("--reasoning-budget") + 1]), ("off", "512"))
            odd = cmd({"reasoning": "maybe; calc", "reasoning_budget": 99999})
            self.assertNotIn("--reasoning", odd)
            self.assertNotIn("--reasoning-budget", odd)
            self.assertNotIn("--check-first", cmd("{broken"))
            self.assertNotIn("--check-first", cmd([1, 2]))

    def test_a_probe_gets_its_own_command_with_validated_options_and_its_result_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            seeds = os.path.join(tmp, "runtime_data", "agent_manager", "seeds")
            os.makedirs(seeds)
            cmd = run_worker.command("py", "rt", tmp, "probe_arbiter")
            self.assertEqual((cmd[1].replace("\\", "/").endswith("benchmarks/probes/arbiter_probe.py"), cmd[2], len(cmd)), (True, tmp, 3))
            with open(os.path.join(seeds, "probe_arbiter.options.json"), "w") as handle:
                json.dump({"models": ["qwen3coder", "swe"], "trials": 2, "extra": "--x"}, handle)
            cmd = run_worker.command("py", "rt", tmp, "probe_arbiter")
            self.assertEqual(cmd[3:], ["--models", "qwen3coder,swe", "--trials", "2"])
            with open(os.path.join(seeds, "probe_arbiter.options.json"), "w") as handle:
                json.dump({"models": ["swe"], "modes": ["escalating", "solo"], "trials": 1}, handle)
            self.assertEqual(run_worker.command("py", "rt", tmp, "probe_arbiter")[3:], ["--models", "swe", "--modes", "escalating,solo", "--trials", "1"])
            with open(os.path.join(seeds, "probe_arbiter.options.json"), "w") as handle:
                json.dump({"models": ["qwen3coder", "swe"], "trials": 2, "extra": "--x"}, handle)
            with open(os.path.join(seeds, "probe_arbiter.options.json"), "w") as handle:
                json.dump({"models": ["a b"], "trials": 99}, handle)
            self.assertEqual(len(run_worker.command("py", "rt", tmp, "probe_arbiter")), 3)
        done = run_worker.summarize("x\nqwen3coder    old_prompt     right 2/6  a: PASS 0\nPROBE DONE\n", 0)
        self.assertEqual((done["state"], done["probe"]), ("succeeded", ["qwen3coder    old_prompt     right 2/6  a: PASS 0"]))
        self.assertEqual(run_worker.summarize("PROBE DONE", 1)["state"], "failed")

    def test_seed_folder_is_found_by_spec_name_only(self):
        self.assertIn("--seed", self.worker_run("hidden test PASSED", 0, seed=True)[1])


if __name__ == "__main__":
    unittest.main()
