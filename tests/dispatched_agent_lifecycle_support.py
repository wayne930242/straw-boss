from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class DispatchedAgentLifecycleFixture:
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        (self.home / ".straw-boss" / "dispatch").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_script(
        self,
        script_name: str,
        *args: str,
        extra_env: dict[str, str] | None = None,
        timeout_seconds: float = 10,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "HOME": str(self.home),
            # The launcher holds its post-start reading open for a few seconds
            # to catch a startup gate herdr has not classified yet; the fake
            # herdr answers instantly, so that window would only buy wall-clock.
            "STRAW_BOSS_AGENT_SETTLE_SECONDS": "0",
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script_name), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

    def write_dispatch(
        self,
        agent_kind: str = "claude",
        main_agent_kind: str = "claude",
        *,
        agent_profile: str | None = None,
        agent_model: str | None = None,
        agent_effort: str | None = None,
        advisor_model: str | None = None,
        slug: str | None = None,
        role: str | None = None,
    ) -> tuple[Path, dict[str, object]]:
        args = [
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            slug or f"contract-{agent_kind}",
            "--task",
            "Implement the requested slice and verify it.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            agent_kind,
            "--main-agent-kind",
            main_agent_kind,
            "--main-agent-pane-id",
            "main-pane",
        ]
        if main_agent_kind == "claude":
            args.extend(["--main-agent-session-id", "main-session"])
        else:
            args.extend(["--main-agent-terminal-id", "terminal-main-pane"])
        for flag, value in (
            ("--agent-profile", agent_profile),
            ("--agent-model", agent_model),
            ("--agent-effort", agent_effort),
            ("--advisor-model", advisor_model),
            ("--role", role),
        ):
            if value is not None:
                args.extend([flag, value])
        result = self.run_script(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        return Path(output["instruction_path"]), output

    def install_fake_herdr(self) -> tuple[Path, Path]:
        fake_bin = self.home / "bin"
        fake_bin.mkdir(exist_ok=True)
        capture = self.home / "herdr-calls.jsonl"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['HERDR_CAPTURE'], 'a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['HERDR_CAPTURE']) as f:\n"
            "    captured = [json.loads(line) for line in f if line.strip()]\n"
            "if args[:2] == ['pane', 'get']:\n"
            "    target = args[2]\n"
            "    print(json.dumps({'result': {'pane': {'pane_id': target, 'tab_id': os.environ.get('HERDR_MAIN_TAB_ID', 'tab-1')}}}))\n"
            "elif args[:2] == ['pane', 'split']:\n"
            "    print(json.dumps({'result': {'pane': {'pane_id': os.environ.get('HERDR_WORKER_PANE_ID', 'worker-pane'), 'tab_id': os.environ.get('HERDR_WORKER_TAB_ID', os.environ.get('HERDR_MAIN_TAB_ID', 'tab-1'))}}}))\n"
            "elif args[:2] == ['pane', 'list']:\n"
            "    print(json.dumps({'result': {'panes': json.loads(os.environ.get('HERDR_PANE_LIST', '[]'))}}))\n"
            "elif args[:2] == ['agent', 'list']:\n"
            "    print(json.dumps({'result': {'agents': json.loads(os.environ.get('HERDR_AGENT_LIST', '[]'))}}))\n"
            "elif args[:2] == ['agent', 'start'] and (args[2] in json.loads(os.environ.get('HERDR_NAME_TAKEN', '[]')) or args[2] in {a.get('name') for a in json.loads(os.environ.get('HERDR_AGENT_LIST', '[]'))}):\n"
            "    print(json.dumps({'error': {'code': 'agent_name_taken', 'message': f'agent name {args[2]} is already used'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'start'] and sum(call[:2] == ['agent', 'start'] for call in captured) <= int(os.environ.get('HERDR_PANE_BUSY_ATTEMPTS', '0')):\n"
            "    print(json.dumps({'error': {'code': 'agent_pane_busy', 'message': f'agent target pane {args[args.index(\"--pane\") + 1]} is not an available shell'}}, separators=(',', ':')), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'start'] and os.environ.get('HERDR_FAIL_START_BLOCKED') == '1':\n"
            "    print(json.dumps({'error': {'code': 'agent_not_ready', 'message': 'agent is blocked during startup'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'start'] and os.environ.get('HERDR_FAIL_START') == '1':\n"
            "    print(json.dumps({'error': {'code': 'agent_start_failed', 'message': 'agent process did not start'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'get'] and os.environ.get('HERDR_FAIL_START') == '1':\n"
            "    print(json.dumps({'error': {'code': 'agent_not_found', 'message': 'no live agent'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'get'] and args[2] in json.loads(os.environ.get('HERDR_MISSING_PANES', '[]')):\n"
            "    print(json.dumps({'error': {'code': 'agent_not_found', 'message': 'no live agent'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'get'] and args[2] in json.loads(os.environ.get('HERDR_AGENT_GET_ERROR_CODES', '{}')):\n"
            "    code = json.loads(os.environ['HERDR_AGENT_GET_ERROR_CODES'])[args[2]]\n"
            "    print(json.dumps({'error': {'code': code, 'message': 'simulated herdr failure'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'get']:\n"
            "    target = args[2]\n"
            "    sessions = json.loads(os.environ.get('HERDR_SESSIONS', '{}'))\n"
            "    session = sessions.get(target, os.environ.get('HERDR_LIVE_SESSION', 'worker-session'))\n"
            "    recovered = any(call[:2] == ['agent', 'send-keys'] for call in captured)\n"
            "    blocked = os.environ.get('HERDR_FAIL_START_BLOCKED') == '1' and not recovered\n"
            "    prompt_positions = [i for i, call in enumerate(captured) if call[:2] == ['agent', 'prompt']]\n"
            "    get_after_prompt = 0\n"
            "    if prompt_positions:\n"
            "        get_after_prompt = sum(call[:2] == ['agent', 'get'] for call in captured[prompt_positions[-1] + 1:])\n"
            "    delay = int(os.environ.get('HERDR_SESSION_DELAY_GETS', '0'))\n"
            "    starts = [call for call in captured if call[:2] == ['agent', 'start'] and call[call.index('--pane') + 1] == target]\n"
            "    started_kind = starts[-1][starts[-1].index('--kind') + 1] if starts else 'claude'\n"
            "    if os.environ.get('HERDR_SESSION_FROM_START') == '1' and starts and '--session-id' in starts[-1]:\n"
            "        session = starts[-1][starts[-1].index('--session-id') + 1]\n"
            "    agent_kinds = json.loads(os.environ.get('HERDR_AGENT_KINDS', '{}'))\n"
            "    terminal_ids = json.loads(os.environ.get('HERDR_TERMINAL_IDS', '{}'))\n"
            "    statuses = json.loads(os.environ.get('HERDR_AGENT_STATUSES', '{}'))\n"
            "    agent_status = statuses.get(target, 'blocked' if blocked else 'idle')\n"
            "    agent = {'name': 'worker', 'agent': agent_kinds.get(target, os.environ.get('HERDR_AGENT_KIND', started_kind)), 'agent_status': agent_status, 'pane_id': target, 'terminal_id': terminal_ids.get(target, os.environ.get('HERDR_TERMINAL_ID', f'terminal-{target}'))}\n"
            "    if target in json.loads(os.environ.get('HERDR_UNNAMED_PANES', '[]')):\n"
            "        del agent['name']\n"
            "    if os.environ.get('HERDR_OMIT_AGENT_SESSION') != '1' and not blocked and (not prompt_positions or get_after_prompt > delay):\n"
            "        agent['agent_session'] = {'value': session}\n"
            "    print(json.dumps({'result': {'agent': agent}}))\n"
            "elif args[:3] == ['pane', 'process-info', '--pane'] and args[3] in json.loads(os.environ.get('HERDR_PROCESS_INFO_ERROR_CODES', '{}')):\n"
            "    code = json.loads(os.environ['HERDR_PROCESS_INFO_ERROR_CODES'])[args[3]]\n"
            "    print(json.dumps({'error': {'code': code, 'message': 'simulated herdr failure'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:3] == ['pane', 'process-info', '--pane']:\n"
            "    target = args[3]\n"
            "    process_infos = json.loads(os.environ.get('HERDR_PROCESS_INFOS', '{}'))\n"
            "    print(json.dumps({'result': {'process_info': process_infos.get(target, {'pane_id': target, 'foreground_processes': []})}}))\n"
            "elif args[:2] == ['pane', 'read']:\n"
            "    print(os.environ.get('HERDR_PANE_TEXT', ''))\n"
            "elif args[:2] == ['agent', 'read']:\n"
            "    target = args[2]\n"
            "    prompts = [call for call in captured if call[:3] == ['agent', 'prompt', target]]\n"
            "    deliver_after = int(os.environ.get('HERDR_TRANSCRIPT_DELIVER_AFTER_PROMPTS', '1'))\n"
            "    if prompts and len(prompts) >= deliver_after:\n"
            "        transcript = prompts[-1][3]\n"
            "        tail_chars = int(os.environ.get('HERDR_TRANSCRIPT_TAIL_CHARS', '0'))\n"
            "        if tail_chars > 0:\n"
            "            transcript = transcript[-tail_chars:]\n"
            "        columns = int(os.environ.get('HERDR_TRANSCRIPT_RENDER_COLUMNS', '0'))\n"
            "        if columns > 0:\n"
            "            rendered = []\n"
            "            for line in transcript.splitlines():\n"
            "                rendered.extend(line[i:i + columns] for i in range(0, len(line), columns))\n"
            "            visible_lines = int(os.environ.get('HERDR_TRANSCRIPT_VISIBLE_LINES', '0'))\n"
            "            if visible_lines > 0:\n"
            "                rendered = rendered[-visible_lines:]\n"
            "            transcript = '\\n'.join(rendered)\n"
            "        print(transcript)\n"
            "    else:\n"
            "        print(os.environ.get('HERDR_TRANSCRIPT_NOISE', 'Ask Codex to do anything'))\n"
            "elif args[:2] == ['agent', 'prompt'] and '--wait' in args and args[2] in json.loads(os.environ.get('HERDR_PROMPT_WAIT_ERROR_CODES', '{}')):\n"
            "    code = json.loads(os.environ['HERDR_PROMPT_WAIT_ERROR_CODES'])[args[2]]\n"
            "    print(json.dumps({'error': {'code': code, 'message': 'simulated herdr failure'}}), file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "elif args[:2] == ['agent', 'prompt'] and args[2] == os.environ.get('HERDR_FAIL_PROMPT_PANE'):\n"
            "    print('prompt failed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "else:\n"
            "    print(json.dumps({'result': {'agent': {'name': 'worker', 'agent_status': 'idle'}}}))\n"
        )
        fake_herdr.chmod(0o755)
        return fake_bin, capture

    def set_worker_endpoint(
        self,
        instruction_path: Path,
        pane: str = "worker-pane",
        session: str = "worker-session",
        terminal_id: str | None = None,
    ) -> dict[str, object]:
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = pane
        if instruction["agent_kind"] == "claude":
            instruction["session_id"] = session
        else:
            instruction["session_id"] = None
            instruction["herdr_terminal_id"] = terminal_id or f"terminal-{pane}"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        return instruction

    def write_coworker(
        self,
        parent_path: Path,
        *,
        slug: str = "coworker-review",
        writable_paths: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        fake_bin, capture = self.install_fake_herdr()
        args = [
            "write",
            "--app",
            "api",
            "--slug",
            slug,
            "--task",
            "Review the real interface with the user and report findings.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            "codex",
            "--parent-instruction-path",
            str(parent_path),
        ]
        for writable_path in writable_paths:
            args.extend(["--writable-path", writable_path])
        return self.run_script(
            "dispatch-task.py",
            *args,
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_ID": "worker-pane",
                "HERDR_SESSIONS": json.dumps(
                    {"worker-pane": "worker-session", "main-pane": "main-session"}
                ),
            },
        )
