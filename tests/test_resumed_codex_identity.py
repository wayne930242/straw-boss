import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from straw_boss.herdr.session import Endpoint, validate_live_session, worker_endpoint_confirmed_closed

class ResumedCodexIdentityTests(unittest.TestCase):
    def live(self, session='original', terminal='new-terminal', provider='codex'):
        agent={'pane_id':'worker-pane','agent':provider,'agent_status':'idle','terminal_id':terminal}
        if session is not None:
            agent['agent_session']={'agent':provider,'kind':'id','value':session}
        return patch('straw_boss.herdr.session.run_herdr', return_value={'result':{'agent':agent}})

    def endpoint(self, session='original'):
        return Endpoint('worker','worker-pane',session,'old-terminal','codex')

    def test_same_session_survives_terminal_restart(self):
        with self.live():
            self.assertEqual(validate_live_session(self.endpoint()),'idle')

    def test_resumed_worker_is_still_live(self):
        with self.live():
            self.assertFalse(worker_endpoint_confirmed_closed(self.endpoint()))

    def test_other_session_cannot_reuse_same_terminal(self):
        with self.live(session='unrelated', terminal='old-terminal'):
            with self.assertRaises(ValueError):
                validate_live_session(self.endpoint())

    def test_missing_recorded_session_cannot_fall_back_to_terminal(self):
        with self.live(session=None, terminal='old-terminal'):
            with self.assertRaises(ValueError):
                validate_live_session(self.endpoint())

    def test_legacy_terminal_still_works(self):
        with self.live(session=None, terminal='old-terminal'):
            self.assertEqual(validate_live_session(self.endpoint(None)),'idle')

    def test_legacy_changed_terminal_needs_explicit_recovery(self):
        with self.live():
            with self.assertRaises(ValueError):
                validate_live_session(self.endpoint(None))

    def test_legacy_terminal_mismatch_is_not_proof_of_closure(self):
        with self.live():
            with self.assertRaisesRegex(ValueError, "cannot confirm closure"):
                worker_endpoint_confirmed_closed(self.endpoint(None))

    def test_wrong_provider_refused(self):
        with self.live(provider='claude'):
            with self.assertRaises(ValueError):
                validate_live_session(self.endpoint())



import json
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class ResumedCodexCliTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def setup_dispatch(self, *, legacy=False):
        path, _ = self.write_dispatch("codex", main_agent_kind="codex")
        d = self.set_worker_endpoint(path)
        if not legacy:
            d.update(session_id="worker-original", main_agent_session_id="main-original")
            path.write_text(json.dumps(d))
        d = json.loads(path.read_text())
        path.with_suffix('.launch.json').write_text(json.dumps({
            "instruction_path":str(path), "contract_sha256":d["contract_sha256"],
            "launched_at":"2026-01-01T00:01:00+00:00",
        }))
        self.evidence_refs=[]
        for target in ("main", "worker"):
            log=self.home/f"{target}-original.jsonl"
            binding={"type":"custom_tool_call_output", "output":{
                "instruction_path":str(path), "contract_sha256":d["contract_sha256"],
            }} if target=="main" else {
                "type":"message", "role":"developer", "content":d["contract_path"],
            }
            records=[{"type":"session_meta","payload":{
                "id":target+"-original","timestamp":"2026-01-01T00:00:00Z",
            }},{"type":"response_item","timestamp":"2026-01-01T00:00:30Z","payload":binding}]
            log.write_text("\n".join(json.dumps(record) for record in records)+"\n")
            self.evidence_refs.append(str(log))
        fake, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture), "HERDR_PANE_ID": "main-pane",
            "HERDR_AGENT_KINDS": json.dumps({"worker-pane":"codex", "main-pane":"codex"}),
            "HERDR_SESSIONS": json.dumps({"worker-pane":"worker-original", "main-pane":"main-original"}),
            "HERDR_TERMINAL_IDS": json.dumps({"worker-pane":"new-worker-terminal", "main-pane":"new-main-terminal"}),
            "HERDR_PROCESS_INFOS": json.dumps({"main-pane": {
                "pane_id":"main-pane", "foreground_processes":[{"pid":os.getpid()}],
            }}),
        }
        return path, env, capture

    def test_status_after_both_terminals_restart_persists_and_notifies(self):
        path, env, capture = self.setup_dispatch()
        result = self.run_script("report-task-status.py", "--instruction-path", str(path),
            "--status", "done", "--note", "Verified resumed completion.",
            extra_env={**env, "HERDR_PANE_ID":"worker-pane"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.with_suffix('.status.json').read_text())["status"],"done")
        calls=[json.loads(line) for line in capture.read_text().splitlines()]
        self.assertTrue(any(call[:3]==["agent","prompt","main-pane"] for call in calls))

    def test_recovery_refuses_to_overwrite_resumed_live_worker(self):
        path, env, _ = self.setup_dispatch()
        result=self.run_script("recover-task-status.py", "--instruction-path", str(path),
            "--status", "done", "--note", "Attempted recovery.", extra_env=env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("still live",result.stderr)
        self.assertFalse(path.with_suffix('.status.json').exists())

    def test_roll_call_recognizes_resumed_worker_and_mine(self):
        path, env, _ = self.setup_dispatch()
        agents=[{"agent":"codex", "pane_id":pane,"terminal_id":"new-"+pane,
                 "agent_session":{"value":session},"agent_status":"idle"}
                for pane,session in [("main-pane","main-original"),("worker-pane","worker-original")]]
        result=self.run_script("roll-call.py","--mine","--json",extra_env={**env,
            "HERDR_AGENT_LIST":json.dumps(agents),"HERDR_PANE_LIST":json.dumps(agents)})
        self.assertEqual(result.returncode,0,result.stderr)
        rows=json.loads(result.stdout)["dispatches"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["verdict"],"running")

    def test_roll_call_rejects_different_session_on_original_terminal(self):
        path, env, _ = self.setup_dispatch()
        agents=[{"agent":"codex","pane_id":"worker-pane","terminal_id":"terminal-worker-pane",
                 "agent_session":{"value":"unrelated"},"agent_status":"idle"}]
        result=self.run_script("roll-call.py","--json",extra_env={**env,
            "HERDR_AGENT_LIST":json.dumps(agents),"HERDR_PANE_LIST":json.dumps(agents)})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["dispatches"][0]["verdict"],"orphaned")

    def rebind(self,path,env,**kwargs):
        return self.run_script("rebind-dispatch.py","--instruction-path",str(path),
            "--main-session-id",kwargs.get("main_session","main-original"),
            "--worker-session-id",kwargs.get("worker_session","worker-original"),
            *[arg for ref in self.evidence_refs for arg in ("--ref",ref)],extra_env=env)

    def test_explicit_legacy_rebind_preserves_receipt_contract_and_status(self):
        path,env,_=self.setup_dispatch(legacy=True)
        before=json.loads(path.read_text())
        receipt=path.with_suffix('.launch.json');receipt_before=receipt.read_bytes()
        result=self.rebind(path,env)
        self.assertEqual(result.returncode,0,result.stderr)
        after=json.loads(path.read_text())
        self.assertEqual(after["session_id"],"worker-original")
        self.assertEqual(after["main_agent_session_id"],"main-original")
        self.assertEqual(after["herdr_terminal_id"],"new-worker-terminal")
        self.assertEqual(after["contract_sha256"],before["contract_sha256"])
        self.assertEqual(after["status"],before["status"])
        self.assertEqual(receipt.read_bytes(),receipt_before)
        self.assertEqual(len(after["routing_rebindings"]),1)

    def test_rebind_mismatch_changes_nothing(self):
        path,env,_=self.setup_dispatch(legacy=True);before=path.read_bytes()
        result=self.rebind(path,env,worker_session="wrong-original")
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(path.read_bytes(),before)

    def test_rebind_cannot_replace_a_recorded_session(self):
        path,env,_=self.setup_dispatch();before=path.read_bytes()
        env["HERDR_SESSIONS"]=json.dumps({"main-pane":"main-original","worker-pane":"other"})
        result=self.rebind(path,env,worker_session="other")
        self.assertNotEqual(result.returncode,0)
        self.assertIn("evidence",result.stderr)
        self.assertEqual(path.read_bytes(),before)

    def test_rebind_requires_coordinator_process_not_just_pane_env(self):
        path,env,_=self.setup_dispatch(legacy=True);before=path.read_bytes()
        env["HERDR_PROCESS_INFOS"]=json.dumps({"main-pane":{
            "pane_id":"main-pane","foreground_processes":[{"pid":99999999}]}})
        result=self.rebind(path,env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("caller process",result.stderr)
        self.assertEqual(path.read_bytes(),before)

    def test_missing_session_is_unknown_not_confirmed_closed(self):
        path,env,_=self.setup_dispatch()
        env["HERDR_SESSIONS"]=json.dumps({"main-pane":"main-original","worker-pane":None})
        result=self.run_script("recover-task-status.py","--instruction-path",str(path),
            "--status","done","--note","Attempted recovery.",extra_env=env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("cannot confirm closure",result.stderr)
        self.assertFalse(path.with_suffix('.status.json').exists())

    def test_moved_session_remains_live_and_roll_call_marks_routing_mismatch(self):
        path,env,_=self.setup_dispatch()
        env["HERDR_SESSIONS"]=json.dumps({"main-pane":"main-original","worker-pane":"other"})
        moved={"agent":"codex","pane_id":"moved-pane","terminal_id":"moved-terminal",
               "agent_session":{"value":"worker-original"},"agent_status":"idle"}
        env["HERDR_AGENT_LIST"]=json.dumps([moved])
        result=self.run_script("recover-task-status.py","--instruction-path",str(path),
            "--status","done","--note","Attempted recovery.",extra_env=env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("still live",result.stderr)
        self.assertFalse(path.with_suffix('.status.json').exists())
        result=self.run_script("roll-call.py","--json",extra_env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["dispatches"][0]["verdict"],"routing-mismatch")

    def test_arbitrary_reference_does_not_authorize_legacy_rebind(self):
        path,env,_=self.setup_dispatch(legacy=True);before=path.read_bytes()
        log=Path(self.evidence_refs[1])
        records=[json.loads(line) for line in log.read_text().splitlines()]
        records[1]["payload"]["role"]="user"
        log.write_text("\n".join(json.dumps(record) for record in records)+"\n")
        result=self.rebind(path,env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("evidence",result.stderr)
        self.assertEqual(path.read_bytes(),before)

    def test_unicode_contract_evidence_is_decoded_before_matching(self):
        path,env,_=self.setup_dispatch(legacy=True)
        d=json.loads(path.read_text());d["contract_path"]+="-訂單"
        path.write_text(json.dumps(d))
        log=Path(self.evidence_refs[1])
        records=[json.loads(line) for line in log.read_text().splitlines()]
        records[1]["payload"]["content"]=d["contract_path"]
        log.write_text("\n".join(json.dumps(record) for record in records)+"\n")
        result=self.rebind(path,env)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_batched_write_and_launch_uses_original_call_time(self):
        path,env,_=self.setup_dispatch(legacy=True)
        log=Path(self.evidence_refs[0])
        records=[json.loads(line) for line in log.read_text().splitlines()]
        records[1]["timestamp"]="2026-01-01T00:02:00Z"
        records[1]["payload"]["call_id"]="launch-call"
        records.insert(1,{"type":"response_item","timestamp":"2026-01-01T00:00:30Z",
            "payload":{"type":"custom_tool_call","call_id":"launch-call",
                       "input":"dispatch-task.py write; launch-dispatched-agent.py"}})
        log.write_text("\n".join(json.dumps(record) for record in records)+"\n")
        result=self.rebind(path,env)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_late_unpaired_tool_output_cannot_claim_old_dispatch(self):
        path,env,_=self.setup_dispatch(legacy=True);before=path.read_bytes()
        log=Path(self.evidence_refs[0])
        records=[json.loads(line) for line in log.read_text().splitlines()]
        records[1]["timestamp"]="2026-01-01T00:02:00Z"
        log.write_text("\n".join(json.dumps(record) for record in records)+"\n")
        result=self.rebind(path,env)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(path.read_bytes(),before)

    def test_launcher_records_worker_and_main_sessions(self):
        path,_=self.write_dispatch("codex",main_agent_kind="codex")
        fake,capture=self.install_fake_herdr()
        env={"PATH":f"{fake}{os.pathsep}{os.environ.get('PATH','')}",
             "HERDR_CAPTURE":str(capture),"HERDR_AGENT_KIND":"codex",
             "HERDR_SESSIONS":json.dumps({"main-pane":"main-original","worker-pane":"worker-original"})}
        result=self.run_script("launch-dispatched-agent.py","--instruction-path",str(path),
            "--name","resumed-worker",extra_env=env,timeout_seconds=20)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads(path.with_suffix('.launch.json').read_text())
        self.assertEqual(receipt["session_id"],"worker-original")
        self.assertEqual(json.loads(path.read_text())["main_agent_session_id"],"main-original")
        result=self.run_script("dispatch-task.py","confirm","--app","api","--slug","contract-codex",extra_env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(path.read_text())["session_id"],"worker-original")

if __name__ == '__main__':
    unittest.main()
