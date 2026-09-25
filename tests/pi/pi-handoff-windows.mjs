import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const root = mkdtempSync(join(tmpdir(), "pi-handoff-windows-"));
const bin = join(root, "bin");
mkdirSync(bin);
writeFileSync(join(bin, "herdr"), `#!/usr/bin/env python3
import json, os, sys, time

from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ["HANDOFF_TEST_DIR"])
stage = {("tab", "create"): "tab", ("pane", "process-info"): "shell", ("agent", "start"): "start", ("agent", "prompt"): "prompt"}.get(tuple(args[:2]))
if stage:
    if stage == "tab":
        for index, value in enumerate(args):
            if value == "--env" and args[index + 1].startswith("PI_HANDOFF_ID="):
                (root / "transfer-id").write_text(args[index + 1].split("=", 1)[1])
    (root / ("entered-" + stage)).write_text("")
    while (root / ("gate-" + stage)).exists() and not (root / ("release-" + stage)).exists():
        time.sleep(0.01)
    if (root / ("fail-" + stage)).exists():
        print(stage + " failed", file=sys.stderr)
        sys.exit(1)
    if stage == "start" and not (root / "skip-ready").exists():
        ready = Path(os.environ["PI_CODING_AGENT_DIR"]) / "handoffs" / ((root / "transfer-id").read_text() + ".ready")
        ready.write_text("receiver")
if args[:2] == ["tab", "create"]:
    print(json.dumps({"result": {"root_pane": {"pane_id": "test:pane"}}}))
elif args[:2] == ["pane", "process-info"]:
    processes = [] if (root / "empty-shell").exists() else [{"name": "zsh"}]
    print(json.dumps({"result": {"process_info": {"foreground_processes": processes}}}))
else:
    print(json.dumps({"result": {}}))
`);
chmodSync(join(bin, "herdr"), 0o755);

const extension = pathToFileURL(resolve("pi/extensions/dispatch-recovery.ts"));
function session(id, file) {
  const handlers = new Map();
  const messages = [];
  const api = { on(event, handler) { handlers.set(event, handler); }, registerTool() {}, sendMessage(message) { messages.push(message); } };
  const ctx = { cwd: root, sessionManager: { getSessionId: () => id, getSessionFile: () => file } };
  return { handlers, messages, api, ctx };
}
async function until(predicate, label, attempts = 120) {
  for (let attempt = 0; attempt < attempts; attempt++) {
    if (predicate()) return;
    await new Promise((done) => setTimeout(done, 50));
  }
  throw new Error(`Timed out waiting for ${label}`);
}

let serial = 0;
async function checkWindow(stage, options = {}) {
  const number = ++serial;
  const home = join(root, `case-${number}`);
  const agentDir = join(home, ".pi", "agent");
  const ledgerDir = join(agentDir, "dispatch-ledger");
  mkdirSync(ledgerDir, { recursive: true });
  process.env.PI_CODING_AGENT_DIR = agentDir;
  if (stage && stage !== "ready" && stage !== "commit") writeFileSync(join(home, `gate-${stage}`), "");
  if (options.fail) writeFileSync(join(home, `fail-${stage}`), "");
  if (options.emptyShell) writeFileSync(join(home, "empty-shell"), "");
  if (options.skipReady || stage === "ready") writeFileSync(join(home, "skip-ready"), "");
  const id = `worker-${number}`;
  const oldId = `old-${number}`;
  const newId = `new-${number}`;
  const child = join(home, "child.jsonl");
  const oldFile = join(home, "old.jsonl");
  const newFile = join(home, "new.jsonl");
  writeFileSync(child, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: id }] } }) + "\n");
  writeFileSync(oldFile, "");
  writeFileSync(newFile, "");
  writeFileSync(join(ledgerDir, `${oldId}.json`), JSON.stringify([{ id, name: id, task: "Finish", cwd: home, sessionFile: child, status: "running" }]));
  const old = session(oldId, oldFile);
  (await import(`${extension.href}?window=${number}-old`)).default(old.api);
  await old.handlers.get("session_start")({ type: "session_start" }, old.ctx);
  const launcher = stage === "commit" ? ["-c", [
    "import importlib.util, os, time",
    "from pathlib import Path",
    "spec = importlib.util.spec_from_file_location('dispatch', os.environ['DISPATCH_SCRIPT'])",
    "dispatch = importlib.util.module_from_spec(spec)",
    "spec.loader.exec_module(dispatch)",
    "original = dispatch.write_json",
    "def gated(path, data):",
    "    if isinstance(data, dict) and data.get('state') == 'committed':",
    "        root = Path(os.environ['HANDOFF_TEST_DIR'])",
    "        (root / 'entered-commit').write_text('')",
    "        while not (root / 'release-commit').exists(): time.sleep(.01)",
    "    return original(path, data)",
    "dispatch.write_json = gated",
    "dispatch.main()",
  ].join("\n")] : [resolve("pi/scripts/pi-dispatch.py")];
  const handoffProcess = spawn("python3", [...launcher, "handoff", "--session-id", oldId, "--cwd", home, "--summary", "Continue"], {
    env: { ...process.env, PI_CODING_AGENT_DIR: agentDir, HERDR_ENV: "1", HANDOFF_TEST_DIR: home, PI_DISPATCH_POLL_SECONDS: "0.05",
      DISPATCH_SCRIPT: resolve("pi/scripts/pi-dispatch.py"), PATH: `${bin}${delimiter}${process.env.PATH}` },
  });
  let stderr = "";
  handoffProcess.stderr.setEncoding("utf8");
  handoffProcess.stderr.on("data", (chunk) => { stderr += chunk; });
  const exit = new Promise((done) => handoffProcess.on("close", done));
  let receiver;
  try {
    if (stage) await until(() => existsSync(join(home, `entered-${stage === "ready" ? "start" : stage}`)), `${stage} entry`);
    if (options.beforeCommit !== false && stage !== "commit") {
      writeFileSync(`${child}.exit`, JSON.stringify({ type: "done" }));
      await until(() => old.messages.length === 1, `old result at ${stage || "ready"}`);
    }
    if (stage === "commit") writeFileSync(`${child}.exit`, JSON.stringify({ type: "done" }));
    if (stage === "ready" && !options.skipReady) {
      const transferId = readFileSync(join(home, "transfer-id"), "utf8");
      writeFileSync(join(agentDir, "handoffs", `${transferId}.ready`), "receiver");
    }
    if (stage && stage !== "ready") writeFileSync(join(home, `release-${stage}`), "");
    const code = await exit;
    const success = !options.fail && !options.emptyShell && !options.skipReady;
    assert.equal(code === 0, success, `${stage}: ${stderr}`);
    const handoffs = join(agentDir, "handoffs");
    const transfer = existsSync(handoffs) ? readdirSync(handoffs).find((name) => name.endsWith(".json")) : undefined;
    if (success) {
      assert.ok(transfer);
      writeFileSync(join(handoffs, transfer.replace(/\.json$/, ".ready")), newId);
      if (options.beforeCommit === false && options.beforeReceiverImport) {
        writeFileSync(`${child}.exit`, JSON.stringify({ type: "done" }));
      }
      process.env.PI_HANDOFF_ID = transfer.replace(/\.json$/, "");
      receiver = session(newId, newFile);
      (await import(`${extension.href}?window=${number}-new`)).default(receiver.api);
      await receiver.handlers.get("session_start")({ type: "session_start" }, receiver.ctx);
      if (options.beforeCommit === false || stage === "commit") {
        if (options.beforeCommit === false && !options.beforeReceiverImport) {
          writeFileSync(`${child}.exit`, JSON.stringify({ type: "done" }));
        }
        await until(() => receiver.messages.length === 1, "receiver result after commit");
      }
    }
    await new Promise((done) => setTimeout(done, 550));
    assert.equal(old.messages.length + (receiver?.messages.length || 0), 1, `single delivery at ${stage || "commit"}`);
    const receiverOwns = options.beforeCommit === false || stage === "commit";
    assert.equal(old.messages.length, receiverOwns ? 0 : 1);
    assert.equal(receiver?.messages.length || 0, receiverOwns ? 1 : 0);
  } finally {
    delete process.env.PI_HANDOFF_ID;
    await old.handlers.get("session_shutdown")();
    if (receiver) await receiver.handlers.get("session_shutdown")();
    rmSync(home, { recursive: true, force: true });
  }
}

try {
  const cases = [
    ...["tab", "shell", "start", "prompt"].map((stage) => [stage, stage, {}]),
    ...["tab", "start", "prompt"].map((stage) => [`${stage}-fail`, stage, { fail: true }]),
    ["shell-fail", "shell", { emptyShell: true }],
    ["ready", "ready", {}],
    ["ready-fail", "ready", { skipReady: true }],
    ["commit", "commit", {}],
    ["after-commit", undefined, { beforeCommit: false }],
    ["after-commit-preimport", undefined, { beforeCommit: false, beforeReceiverImport: true }],
  ];
  for (const [name, stage, options] of cases) {
    if (!process.env.PI_HANDOFF_WINDOW || process.env.PI_HANDOFF_WINDOW === name) {
      await checkWindow(stage, options);
    }
  }
} finally {
  delete process.env.PI_HANDOFF_ID;
  rmSync(root, { recursive: true, force: true });
}
