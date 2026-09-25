import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { rmSync } from "node:fs";

// The extension skips dispatch_control inside a subagent; isolate from the caller's environment.
delete process.env.PI_SUBAGENT_ID;

const home = mkdtempSync(join(tmpdir(), "pi-dispatch-"));
process.env.PI_CODING_AGENT_DIR = join(home, ".pi", "agent");
const parent = join(home, "parent.jsonl");
const child = join(home, "child.jsonl");
writeFileSync(parent, "");

function session(id = "parent-1", file = parent) {
  const handlers = new Map();
  const messages = [];
  const tools = new Map();
  const api = {
    on(event, handler) { handlers.set(event, handler); },
    sendMessage(message, options) { messages.push({ message, options }); },
    registerTool(tool) { tools.set(tool.name, tool); },
  };
  const ctx = {
    cwd: home,
    sessionManager: { getSessionId: () => id, getSessionFile: () => file },
  };
  return { handlers, messages, tools, api, ctx };
}

try {
  const extension = pathToFileURL(resolve("pi/extensions/dispatch-recovery.ts"));
  const first = session();
  (await import(extension.href)).default(first.api);
  await first.handlers.get("session_start")({ type: "session_start", reason: "startup" }, first.ctx);
  const inventory = await first.tools.get("dispatch_control").execute("call-1", { action: "roll-call" }, null, null, first.ctx);
  assert.match(inventory.content[0].text, /No recorded dispatches/);
  await first.handlers.get("tool_result")({
    toolName: "subagent", isError: false,
    details: { status: "started", id: "child-1", name: "worker", task: "Do work", sessionFile: child },
    input: { cwd: home },
  }, first.ctx);
  const ledger = join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/parent-1.json");
  assert.equal(JSON.parse(readFileSync(ledger))[0].status, "running");

  delete globalThis.__weihungDispatchSessions;
  const resumed = session();
  (await import(`${extension.href}?restart=1`)).default(resumed.api);
  await resumed.handlers.get("session_start")({ type: "session_start", reason: "resume" }, resumed.ctx);
  writeFileSync(child, [
    JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "Task complete" }] } }),
  ].join("\n") + "\n");
  writeFileSync(`${child}.exit`, JSON.stringify({ type: "done" }));
  for (let attempt = 0; attempt < 20 && resumed.messages.length === 0; attempt++) {
    await new Promise((done) => setTimeout(done, 100));
  }
  assert.equal(JSON.parse(readFileSync(ledger))[0].status, "done");
  assert.equal(resumed.messages.length, 1);
  assert.match(resumed.messages[0].message.content, /Task complete/);
  assert.equal(resumed.messages[0].options.triggerTurn, true);
  await resumed.handlers.get("session_shutdown")();

  const parent2 = join(home, "parent2.jsonl");
  const child2 = join(home, "child2.jsonl");
  writeFileSync(parent2, JSON.stringify({
    type: "custom_message", customType: "subagent_result",
    details: { sessionFile: child2, exitCode: 0 },
  }) + "\n");
  const ledger2 = join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/parent-2.json");
  writeFileSync(ledger2, JSON.stringify([{ id: "child-2", name: "worker2", task: "Done", cwd: home, sessionFile: child2, status: "running" }]));
  delete globalThis.__weihungDispatchSessions;
  const reconciled = session("parent-2", parent2);
  (await import(`${extension.href}?restart=2`)).default(reconciled.api);
  await reconciled.handlers.get("session_start")({ type: "session_start", reason: "resume" }, reconciled.ctx);
  assert.equal(JSON.parse(readFileSync(ledger2))[0].status, "done");
  assert.equal(JSON.parse(readFileSync(ledger2))[0].delivered, true);
  assert.equal(reconciled.messages.length, 0);
  await reconciled.handlers.get("session_shutdown")();

  const transferredChild = join(home, "transferred-child.jsonl");
  writeFileSync(transferredChild, "");
  const oldParent = join(home, "old-parent.jsonl");
  const newParent = join(home, "new-parent.jsonl");
  writeFileSync(oldParent, "");
  writeFileSync(newParent, "");
  const transferred = { id: "transferred-1", name: "worker3", task: "Wait", cwd: home,
    sessionFile: transferredChild, status: "transferred" };
  writeFileSync(join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/old-parent.json"), JSON.stringify([transferred]));
  const old = session("old-parent", oldParent);
  (await import(`${extension.href}?transfer=old`)).default(old.api);
  const native = { role: "custom", customType: "subagent_result", content: "NATIVE_RESULT",
    details: { sessionFile: transferredChild, exitCode: 0, resultContent: "NATIVE_RESULT" } };
  const replacement = await old.handlers.get("message_end")({ type: "message_end", message: native }, old.ctx);
  assert.equal(replacement.message.customType, "transferred_dispatch_notice");
  assert.doesNotMatch(replacement.message.content, /NATIVE_RESULT/);

  const handoffDir = join(process.env.PI_CODING_AGENT_DIR, "handoffs");
  const { mkdirSync } = await import("node:fs");
  mkdirSync(handoffDir, { recursive: true });
  writeFileSync(join(handoffDir, "transfer-1.json"), JSON.stringify({ from: "old-parent", state: "committed", dispatches: [{ ...transferred, status: "running" }] }));
  writeFileSync(join(handoffDir, "transfer-1.ready"), "new-parent");
  process.env.PI_HANDOFF_ID = "transfer-1";
  const receiving = session("new-parent", newParent);
  (await import(`${extension.href}?transfer=new`)).default(receiving.api);
  await receiving.handlers.get("session_start")({ type: "session_start", reason: "startup" }, receiving.ctx);
  for (let attempt = 0; attempt < 20 && receiving.messages.length === 0; attempt++) {
    await new Promise((done) => setTimeout(done, 100));
  }
  assert.equal(receiving.messages.length, 1);
  assert.match(receiving.messages[0].message.content, /NATIVE_RESULT/);
  assert.equal(JSON.parse(readFileSync(join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/new-parent.json")))[0].delivered, true);
  await receiving.handlers.get("session_shutdown")();
  delete process.env.PI_HANDOFF_ID;

  const partialParent = join(home, "partial-parent.jsonl");
  const partialChild = join(home, "partial-child.jsonl");
  writeFileSync(partialParent, "");
  writeFileSync(partialChild, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "PARTIAL_RESULT" }] } }) + "\n");
  const partialLedger = join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/partial-parent.json");
  writeFileSync(partialLedger, JSON.stringify([{ id: "partial-child", name: "partial-worker", task: "Done", cwd: home,
    sessionFile: partialChild, status: "running" }]));
  writeFileSync(`${partialChild}.exit`, "{");
  const partial = session("partial-parent", partialParent);
  (await import(`${extension.href}?partial=1`)).default(partial.api);
  await partial.handlers.get("session_start")({ type: "session_start", reason: "startup" }, partial.ctx);
  assert.equal(JSON.parse(readFileSync(partialLedger))[0].status, "running", "a partial completion file must be retried");
  writeFileSync(`${partialChild}.exit`, JSON.stringify({ type: "done" }));
  for (let attempt = 0; attempt < 20 && partial.messages.length === 0; attempt++) {
    await new Promise((done) => setTimeout(done, 100));
  }
  assert.equal(partial.messages.length, 1);
  assert.equal(JSON.parse(readFileSync(partialLedger))[0].status, "done");
  await partial.handlers.get("session_shutdown")();

  const retryParent = join(home, "retry-parent.jsonl");
  const retryChild = join(home, "retry-child.jsonl");
  writeFileSync(retryParent, "");
  writeFileSync(retryChild, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "RETRY_RESULT" }] } }) + "\n");
  writeFileSync(`${retryChild}.exit`, JSON.stringify({ type: "done" }));
  const retryLedger = join(process.env.PI_CODING_AGENT_DIR, "dispatch-ledger/retry-parent.json");
  writeFileSync(retryLedger, JSON.stringify([{ id: "retry-child", name: "retry-worker", task: "Done", cwd: home,
    sessionFile: retryChild, status: "running" }]));
  const retry = session("retry-parent", retryParent);
  let attempts = 0;
  retry.api.sendMessage = (message, options) => {
    if (++attempts === 1) throw new Error("injected send failure");
    retry.messages.push({ message, options });
  };
  (await import(`${extension.href}?retry=1`)).default(retry.api);
  const originalError = console.error;
  console.error = () => {};
  try {
    await retry.handlers.get("session_start")({ type: "session_start", reason: "startup" }, retry.ctx);
    assert.equal(JSON.parse(readFileSync(retryLedger))[0].status, "running");
    for (let attempt = 0; attempt < 20 && retry.messages.length === 0; attempt++) {
      await new Promise((done) => setTimeout(done, 100));
    }
  } finally {
    console.error = originalError;
  }
  assert.equal(attempts, 2);
  assert.equal(retry.messages.length, 1);
  assert.equal(JSON.parse(readFileSync(retryLedger))[0].status, "done");
  await retry.handlers.get("session_shutdown")();
} finally {
  rmSync(home, { recursive: true, force: true });
}
