import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const extension = pathToFileURL(resolve("pi/extensions/dispatch-recovery.ts"));
const mode = process.argv[2];

if (mode === "receiver" || mode === "resume") {
  const root = process.env.HANDOFF_TEST_DIR;
  const handlers = new Map();
  const messages = [];
  const api = {
    on(event, handler) { handlers.set(event, handler); },
    registerTool() {},
    sendMessage(message) { messages.push(message); },
  };
  const ctx = {
    cwd: root,
    sessionManager: {
      getSessionId: () => "receiver-session",
      getSessionFile: () => join(root, "receiver.jsonl"),
    },
  };
  (await import(extension.href)).default(api);
  await handlers.get("session_start")({ type: "session_start" }, ctx);
  if (mode === "receiver") {
    // Hold the event loop after readiness so the parent can commit and kill us before import.
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 30_000);
  } else {
    for (let attempt = 0; attempt < 40 && messages.length === 0; attempt++) {
      await new Promise((done) => setTimeout(done, 50));
    }
    writeFileSync(join(root, "received.json"), JSON.stringify(messages));
    await handlers.get("session_shutdown")();
  }
} else {
  const root = mkdtempSync(join(tmpdir(), "pi-handoff-resume-"));
  const agent = join(root, "agent");
  const handoffs = join(agent, "handoffs");
  const ledger = join(agent, "dispatch-ledger", "receiver-session.json");
  const child = join(root, "child.jsonl");
  mkdirSync(handoffs, { recursive: true });
  writeFileSync(join(root, "receiver.jsonl"), "");
  writeFileSync(child, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "FINISHED" }] } }) + "\n");
  writeFileSync(join(handoffs, "transfer.json"), JSON.stringify({ from: "old-session", state: "pending" }));
  writeFileSync(join(handoffs, "unrelated.ready"), "other-session");
  writeFileSync(join(handoffs, "unrelated.json"), JSON.stringify({
    from: "another-owner", state: "committed", dispatches: [{
      id: "unrelated-worker", name: "unrelated-worker", task: "Other scope", cwd: root,
      sessionFile: child, status: "running",
    }],
  }));
  const env = { ...process.env, HANDOFF_TEST_DIR: root, PI_CODING_AGENT_DIR: agent };
  const first = spawn(process.execPath, ["--experimental-strip-types", process.argv[1], "receiver"], {
    env: { ...env, PI_HANDOFF_ID: "transfer" }, stdio: "ignore",
  });
  const firstExit = new Promise((done) => first.on("close", done));
  try {
    const ready = join(handoffs, "transfer.ready");
    for (let attempt = 0; attempt < 100 && !existsSync(ready); attempt++) {
      await new Promise((done) => setTimeout(done, 50));
    }
    assert.equal(readFileSync(ready, "utf8"), "receiver-session");
    writeFileSync(join(handoffs, "transfer.json"), JSON.stringify({
      from: "old-session", state: "committed", dispatches: [{
        id: "worker", name: "worker", task: "Finish", cwd: root,
        sessionFile: child, status: "running",
      }],
    }));
    first.kill("SIGKILL");
    await firstExit;
    assert.equal(existsSync(ledger), false, "the first process must die before import");
    writeFileSync(`${child}.exit`, JSON.stringify({ type: "done", content: "FINISHED" }));
    const resumed = spawn(process.execPath, ["--experimental-strip-types", process.argv[1], "resume"], {
      env: { ...env, PI_HANDOFF_ID: "" }, stdio: "inherit",
    });
    const resumedCode = await new Promise((done) => resumed.on("close", done));
    assert.equal(resumedCode, 0);
    const records = JSON.parse(readFileSync(ledger, "utf8"));
    assert.equal(records.length, 1, "only the session named by the ready marker imports the handoff");
    assert.equal(records[0].status, "done");
    assert.equal(existsSync(ready), false, "the imported handoff no longer needs its readiness marker");
    assert.equal(JSON.parse(readFileSync(join(root, "received.json"), "utf8")).length, 1);
  } finally {
    first.kill("SIGKILL");
    rmSync(root, { recursive: true, force: true });
  }
}
