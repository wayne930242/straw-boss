import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const home = mkdtempSync(join(tmpdir(), "pi-handoff-race-"));
const agentDir = join(home, ".pi", "agent");
const ledgerDir = join(agentDir, "dispatch-ledger");
const binDir = join(home, "bin");
mkdirSync(ledgerDir, { recursive: true });
mkdirSync(binDir);
process.env.PI_CODING_AGENT_DIR = agentDir;

const fakeHerdr = join(binDir, "herdr");
writeFileSync(fakeHerdr, `#!/usr/bin/env python3
import json, os, sys, time

from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ["HANDOFF_TEST_DIR"])
if args[:2] == ["tab", "create"]:
    for index, value in enumerate(args):
        if value == "--env" and args[index + 1].startswith("PI_HANDOFF_ID="):
            (root / "transfer-id").write_text(args[index + 1].split("=", 1)[1])
    (root / "pane-created").write_text("")
    for _ in range(100):
        if (root / "release-pane").exists():
            break
        time.sleep(0.05)
    if (root / "fail-pane").exists():
        print("tab creation failed", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"result": {"root_pane": {"pane_id": "test:pane"}}}))
elif args[:2] == ["pane", "process-info"]:
    print(json.dumps({"result": {"process_info": {"foreground_processes": [{"name": "zsh"}]}}}))
elif args[:2] == ["agent", "start"]:
    transfer_id = (root / "transfer-id").read_text()
    (Path(os.environ["PI_CODING_AGENT_DIR"]) / "handoffs" / (transfer_id + ".ready")).write_text("receiver")
    print(json.dumps({"result": {}}))
else:
    print(json.dumps({"result": {}}))
`);
chmodSync(fakeHerdr, 0o755);

function session(id, file) {
  const handlers = new Map();
  const messages = [];
  const api = {
    on(event, handler) { handlers.set(event, handler); },
    registerTool() {},
    sendMessage(message) { messages.push(message); },
  };
  const ctx = { cwd: home, sessionManager: { getSessionId: () => id, getSessionFile: () => file } };
  return { handlers, messages, api, ctx };
}

async function until(predicate, label) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (predicate()) return;
    await new Promise((done) => setTimeout(done, 50));
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function runHandoff(owner) {
  const child = spawn("python3", [resolve("pi/scripts/pi-dispatch.py"), "handoff", "--session-id", owner, "--cwd", home, "--summary", "Continue"], {
    env: { ...process.env, PI_CODING_AGENT_DIR: agentDir, HERDR_ENV: "1", HANDOFF_TEST_DIR: home,
      PATH: `${binDir}${delimiter}${process.env.PATH}` },
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const exit = new Promise((done) => child.on("close", done));
  await until(() => existsSync(join(home, "pane-created")), "pane creation");
  return { exit, stderr: () => stderr };
}

try {
  const childFile = join(home, "child.jsonl");
  const oldFile = join(home, "old.jsonl");
  const newFile = join(home, "new.jsonl");
  writeFileSync(childFile, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "RACE_RESULT" }] } }) + "\n");
  writeFileSync(oldFile, "");
  writeFileSync(newFile, "");
  writeFileSync(join(ledgerDir, "old.json"), JSON.stringify([{
    id: "worker-race", name: "worker", task: "Complete during handoff", cwd: home,
    sessionFile: childFile, status: "running",
  }]));

  const extension = pathToFileURL(resolve("pi/extensions/dispatch-recovery.ts"));
  const old = session("old", oldFile);
  (await import(extension.href)).default(old.api);
  await old.handlers.get("session_start")({ type: "session_start", reason: "startup" }, old.ctx);

  const handoff = await runHandoff("old");
  writeFileSync(`${childFile}.exit`, JSON.stringify({ type: "done" }));
  await until(() => old.messages.length === 1, "original owner result before commit");
  writeFileSync(join(home, "release-pane"), "");
  assert.equal(await handoff.exit, 0, handoff.stderr());

  const handoffFile = readdirSync(join(agentDir, "handoffs")).find((name) => name.endsWith(".json"));
  writeFileSync(join(agentDir, "handoffs", handoffFile.replace(/\.json$/, ".ready")), "new");
  process.env.PI_HANDOFF_ID = handoffFile.replace(/\.json$/, "");
  const receiver = session("new", newFile);
  (await import(`${extension.href}?race=receiver`)).default(receiver.api);
  await receiver.handlers.get("session_start")({ type: "session_start", reason: "startup" }, receiver.ctx);
  assert.equal(old.messages.length + receiver.messages.length, 1, "a completion during handoff must reach one owner");
  assert.equal(old.messages.length, 1);
  assert.match(old.messages[0].content, /RACE_RESULT/);
  await old.handlers.get("session_shutdown")();
  await receiver.handlers.get("session_shutdown")();
  delete process.env.PI_HANDOFF_ID;

  unlinkSync(join(home, "pane-created"));
  unlinkSync(join(home, "release-pane"));
  writeFileSync(join(home, "fail-pane"), "");
  const failedChild = join(home, "failed-child.jsonl");
  const failedParent = join(home, "failed-parent.jsonl");
  writeFileSync(failedChild, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "FAILED_HANDOFF_RESULT" }] } }) + "\n");
  writeFileSync(failedParent, "");
  writeFileSync(join(ledgerDir, "old-fail.json"), JSON.stringify([{
    id: "worker-fail", name: "worker-fail", task: "Complete during failed handoff", cwd: home,
    sessionFile: failedChild, status: "running",
  }]));
  const failedOwner = session("old-fail", failedParent);
  (await import(`${extension.href}?race=failed-owner`)).default(failedOwner.api);
  await failedOwner.handlers.get("session_start")({ type: "session_start", reason: "startup" }, failedOwner.ctx);
  const failedHandoff = await runHandoff("old-fail");
  writeFileSync(`${failedChild}.exit`, JSON.stringify({ type: "done" }));
  writeFileSync(join(home, "release-pane"), "");
  assert.notEqual(await failedHandoff.exit, 0);
  await until(() => failedOwner.messages.length > 0, "original owner result after failed handoff");
  assert.equal(failedOwner.messages.length, 1);
  assert.match(failedOwner.messages[0].content, /FAILED_HANDOFF_RESULT/);
  assert.equal(JSON.parse(readFileSync(join(ledgerDir, "old-fail.json"), "utf8"))[0].delivered, true);
  await failedOwner.handlers.get("session_shutdown")();
} finally {
  delete process.env.PI_HANDOFF_ID;
  rmSync(home, { recursive: true, force: true });
}
