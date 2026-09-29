import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const home = mkdtempSync(join(tmpdir(), "pi-recovery-pane-"));
process.env.PI_CODING_AGENT_DIR = join(home, ".pi", "agent");

// A fake herdr: `pane list` serves the pane state file, `pane close` records the call.
const state = join(home, "panes.json");
const calls = join(home, "calls.log");
const fakeHerdr = join(home, "herdr");
writeFileSync(fakeHerdr, `#!/usr/bin/env node
const fs = require("node:fs");
const [, , group, action, pane] = process.argv;
if (group === "pane" && action === "list") {
  process.stdout.write(JSON.stringify({ result: { panes: JSON.parse(fs.readFileSync(${JSON.stringify(state)}, "utf8")) } }));
} else if (group === "pane" && action === "close") {
  fs.appendFileSync(${JSON.stringify(calls)}, "close " + pane + "\\n");
}
`);
chmodSync(fakeHerdr, 0o755);
process.env.HERDR_BIN_PATH = fakeHerdr;
const setPanes = (panes) => writeFileSync(state, JSON.stringify(panes));
const closed = () => existsSync(calls) ? readFileSync(calls, "utf8").split("\n").filter(Boolean) : [];
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

const parent = join(home, "parent.jsonl");
writeFileSync(parent, "");

function session(id = "parent-1") {
  const handlers = new Map();
  const messages = [];
  const api = {
    on(event, handler) { handlers.set(event, handler); },
    sendMessage(message, options) { messages.push({ message, options }); },
    registerTool() {},
  };
  const ctx = { cwd: home, sessionManager: { getSessionId: () => id, getSessionFile: () => parent } };
  return { handlers, messages, api, ctx };
}

const extension = pathToFileURL(resolve("pi/extensions/dispatch-recovery.ts"));
let restarts = 0;
async function restart() {
  delete globalThis.__weihungDispatchSessions;
  const next = session();
  (await import(`${extension.href}?restart=${++restarts}`)).default(next.api);
  await next.handlers.get("session_start")({ type: "session_start", reason: "resume" }, next.ctx);
  return next;
}

function finish(childFile) {
  writeFileSync(childFile, JSON.stringify({
    type: "message", message: { role: "assistant", content: [{ type: "text", text: "Task complete" }] },
  }) + "\n");
  writeFileSync(`${childFile}.exit`, JSON.stringify({ type: "done" }));
}

async function delivered(current, count) {
  for (let attempt = 0; attempt < 30 && current.messages.length < count; attempt++) await sleep(100);
  assert.equal(current.messages.length, count);
}

try {
  const ledger = join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/parent-1.json");

  // A resume launch script has no PI_SUBAGENT_SURFACE; the pane is found by its dispatch label.
  const first = session();
  (await import(extension.href)).default(first.api);
  await first.handlers.get("session_start")({ type: "session_start", reason: "startup" }, first.ctx);
  const resumedChild = join(home, "resumed.jsonl");
  const resumeScript = join(home, "resume.sh");
  writeFileSync(resumeScript, "PI_SUBAGENT_NAME='worker-r' pi --session resumed.jsonl\n");
  setPanes([{ pane_id: "w:p1", label: "worker-r", agent: "pi" }, { pane_id: "w:p0", agent: "pi" }]);
  await first.handlers.get("tool_result")({
    toolName: "subagent_resume", isError: false,
    details: { status: "started", id: "r1", name: "worker-r", sessionPath: resumedChild, launchScriptFile: resumeScript },
    input: { message: "Continue" },
  }, first.ctx);
  assert.equal(JSON.parse(readFileSync(ledger))[0].paneId, "w:p1");

  // An ambiguous label records no pane rather than guessing.
  setPanes([{ pane_id: "w:p2", label: "twin", agent: "pi" }, { pane_id: "w:p3", label: "twin", agent: "pi" }]);
  await first.handlers.get("tool_result")({
    toolName: "subagent", isError: false,
    details: { status: "started", id: "t1", name: "twin", task: "Do work", sessionFile: join(home, "twin.jsonl") },
    input: { cwd: home },
  }, first.ctx);
  assert.equal(JSON.parse(readFileSync(ledger)).find((record) => record.id === "t1").paneId, undefined);
  await first.handlers.get("session_shutdown")();

  // After a parent restart, a recovered delivery closes the worker pane once its agent has exited.
  setPanes([{ pane_id: "w:p1", label: "worker-r" }, { pane_id: "w:p0", agent: "pi" }]);
  const recovered = await restart();
  finish(resumedChild);
  await delivered(recovered, 1);
  assert.match(recovered.messages[0].message.content, /Recovered dispatch worker-r/);
  assert.deepEqual(closed(), ["close w:p1"]);
  await recovered.handlers.get("session_shutdown")();

  // A pane whose agent is still shutting down stays open until the agent is gone.
  const liveChild = join(home, "live.jsonl");
  writeFileSync(ledger, JSON.stringify([
    { id: "l1", name: "worker-l", task: "Do work", cwd: home, sessionFile: liveChild, paneId: "w:p4", status: "running" },
  ]));
  setPanes([{ pane_id: "w:p4", label: "worker-l", agent: "pi" }]);
  const lingering = await restart();
  finish(liveChild);
  await delivered(lingering, 1);
  await sleep(300);
  assert.deepEqual(closed(), ["close w:p1"], "a pane with a live agent is not closed");
  setPanes([{ pane_id: "w:p4", label: "worker-l" }]);
  for (let attempt = 0; attempt < 30 && closed().length < 2; attempt++) await sleep(100);
  assert.deepEqual(closed(), ["close w:p1", "close w:p4"]);
  await lingering.handlers.get("session_shutdown")();

  // A pane that is already gone is left alone.
  const goneChild = join(home, "gone.jsonl");
  writeFileSync(ledger, JSON.stringify([
    { id: "g1", name: "worker-g", task: "Do work", cwd: home, sessionFile: goneChild, paneId: "w:p5", status: "running" },
  ]));
  setPanes([]);
  const gone = await restart();
  finish(goneChild);
  await delivered(gone, 1);
  await sleep(200);
  assert.deepEqual(closed(), ["close w:p1", "close w:p4"]);
  await gone.handlers.get("session_shutdown")();
} finally {
  rmSync(home, { recursive: true, force: true });
}
