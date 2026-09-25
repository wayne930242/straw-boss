import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const home = mkdtempSync(join(tmpdir(), "pi-ledger-concurrency-"));
const agentDir = join(home, "agent");
const ledgerDir = join(agentDir, "dispatch-ledger");
mkdirSync(ledgerDir, { recursive: true });
const extension = resolve("pi/extensions/dispatch-recovery.ts");

function child(script, env) {
  const process = spawn("node", ["--experimental-strip-types", "--input-type=module", "-e", script], {
    env: { ...globalThis.process.env, PI_CODING_AGENT_DIR: agentDir, TEST_HOME: home, EXTENSION: extension, ...env },
  });
  let stderr = "";
  process.stderr.setEncoding("utf8");
  process.stderr.on("data", (chunk) => { stderr += chunk; });
  return { exit: new Promise((done) => process.on("close", done)), stderr: () => stderr };
}

async function until(predicate, label) {
  for (let attempt = 0; attempt < 200; attempt++) {
    if (predicate()) return;
    await new Promise((done) => setTimeout(done, 10));
  }
  throw new Error(`Timed out waiting for ${label}`);
}

try {
  const parent = join(home, "parent.jsonl");
  writeFileSync(parent, "");
  const parseErrors = [];
  const sample = setInterval(() => {
    const path = join(ledgerDir, "owner.json");
    if (existsSync(path)) {
      try { JSON.parse(readFileSync(path, "utf8")); }
      catch (error) { parseErrors.push(error); }
    }
  }, 1);
  sample.unref();
  const writers = Array.from({ length: 16 }, (_, index) => child(`
    import { pathToFileURL } from 'node:url';
    const handlers = new Map();
    const pi = { on(name, handler) { handlers.set(name, handler); }, registerTool() {} };
    (await import(pathToFileURL(process.env.EXTENSION).href)).default(pi);
    const ctx = { cwd: process.env.TEST_HOME, sessionManager: {
      getSessionId: () => 'owner', getSessionFile: () => process.env.TEST_HOME + '/parent.jsonl',
    } };
    await handlers.get('tool_result')({ toolName: 'subagent', isError: false,
      details: { status: 'started', id: process.env.CHILD_ID, name: process.env.CHILD_ID,
        task: 'Finish', sessionFile: process.env.TEST_HOME + '/' + process.env.CHILD_ID + '.jsonl' },
      input: { cwd: process.env.TEST_HOME },
    }, ctx);
  `, { CHILD_ID: `child-${index}` }));
  for (const writer of writers) assert.equal(await writer.exit, 0, writer.stderr());
  clearInterval(sample);
  assert.equal(parseErrors.length, 0, "readers always observe a complete ledger JSON value");
  const records = JSON.parse(readFileSync(join(ledgerDir, "owner.json"), "utf8"));
  assert.equal(records.length, 16, "concurrent registration preserves every dispatch");

  const sidecar = join(home, "result.jsonl");
  writeFileSync(sidecar, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "RESULT" }] } }) + "\n");
  writeFileSync(`${sidecar}.exit`, JSON.stringify({ type: "done" }));
  for (const sessionId of ["receiver-a", "receiver-b"]) {
    writeFileSync(join(home, `${sessionId}.jsonl`), "");
    writeFileSync(join(ledgerDir, `${sessionId}.json`), JSON.stringify([{
      id: "shared-worker", name: "shared-worker", task: "Finish", cwd: home,
      sessionFile: sidecar, status: "running",
    }]));
  }
  const receiverScript = `
    import { appendFileSync, existsSync, writeFileSync } from 'node:fs';
    import { pathToFileURL } from 'node:url';
    const handlers = new Map();
    const pi = {
      on(name, handler) { handlers.set(name, handler); }, registerTool() {},
      sendMessage() {
        const wait = new Int32Array(new SharedArrayBuffer(4));
        Atomics.wait(wait, 0, 0, 200);
        appendFileSync(process.env.TEST_HOME + '/deliveries', process.env.SESSION_ID + '\\n');
      },
    };
    (await import(pathToFileURL(process.env.EXTENSION).href)).default(pi);
    writeFileSync(process.env.TEST_HOME + '/ready-' + process.env.SESSION_ID, '');
    while (!existsSync(process.env.TEST_HOME + '/go')) {
      const wait = new Int32Array(new SharedArrayBuffer(4));
      Atomics.wait(wait, 0, 0, 10);
    }
    const ctx = { cwd: process.env.TEST_HOME, sessionManager: {
      getSessionId: () => process.env.SESSION_ID,
      getSessionFile: () => process.env.TEST_HOME + '/' + process.env.SESSION_ID + '.jsonl',
    } };
    await handlers.get('session_start')({ type: 'session_start' }, ctx);
    await handlers.get('session_shutdown')();
  `;
  const receivers = ["receiver-a", "receiver-b"].map((sessionId) => child(receiverScript, { SESSION_ID: sessionId }));
  await until(() => ["receiver-a", "receiver-b"].every((id) => existsSync(join(home, `ready-${id}`))), "both receivers");
  writeFileSync(join(home, "go"), "");
  for (const receiver of receivers) assert.equal(await receiver.exit, 0, receiver.stderr());
  assert.equal(readFileSync(join(home, "deliveries"), "utf8").trim().split("\n").length, 1,
    "a shared dispatch marker allows one cross-process delivery");
} finally {
  rmSync(home, { recursive: true, force: true });
}
