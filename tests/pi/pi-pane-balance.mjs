import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import paneBalance, { balanceAfterClose, balanceTab, planBalance, spawnAfterClose } from "../../pi/extensions/pane-balance.ts";

const rect = (x, y, width, height) => ({ x, y, width, height });

// pi-herdr-agents splits each worker off the parent pane, so three workers leave a chain of halves.
const chain = {
  splits: [
    { id: "split_0_root", direction: "right", ratio: 0.5, rect: rect(0, 0, 183, 62) },
    { id: "split_1_0", direction: "right", ratio: 0.5, rect: rect(0, 0, 92, 62) },
    { id: "split_2_00", direction: "right", ratio: 0.5, rect: rect(0, 0, 46, 62) },
  ],
  panes: [
    { pane_id: "lead", rect: rect(0, 0, 23, 62) },
    { pane_id: "w3", rect: rect(23, 0, 23, 62) },
    { pane_id: "w2", rect: rect(46, 0, 46, 62) },
    { pane_id: "w1", rect: rect(92, 0, 91, 62) },
  ],
};
assert.deepEqual(planBalance(chain), [
  { pane: "w2", direction: "right", amount: 0.25 },
  { pane: "w3", direction: "right", amount: 0.1667 },
], "a chain of halves becomes four equal columns");

assert.deepEqual(planBalance({ splits: [], panes: [{ pane_id: "lead", rect: rect(0, 0, 183, 62) }] }), [],
  "a lone pane needs nothing");

const balanced = {
  splits: [
    { id: "split_0_root", direction: "right", ratio: 0.5, rect: rect(0, 0, 180, 60) },
  ],
  panes: [{ pane_id: "lead", rect: rect(0, 0, 90, 60) }, { pane_id: "w1", rect: rect(90, 0, 90, 60) }],
};
assert.deepEqual(planBalance(balanced), [], "equal columns stay put");

// A worker closed on the left of a 3:1 split shrinks the first side, so the second side grows back.
const afterClose = {
  splits: [{ id: "split_0_root", direction: "right", ratio: 0.75, rect: rect(0, 0, 180, 60) }],
  panes: [{ pane_id: "lead", rect: rect(0, 0, 135, 60) }, { pane_id: "w1", rect: rect(135, 0, 45, 60) }],
};
assert.deepEqual(planBalance(afterClose), [{ pane: "w1", direction: "left", amount: 0.25 }]);

// A stacked pair counts as one column; the stacked split balances its own rows.
const stacked = {
  splits: [
    { id: "split_0_root", direction: "right", ratio: 0.5, rect: rect(0, 0, 180, 60) },
    { id: "split_1_1", direction: "down", ratio: 0.7, rect: rect(90, 0, 90, 60) },
  ],
  panes: [
    { pane_id: "lead", rect: rect(0, 0, 90, 60) },
    { pane_id: "top", rect: rect(90, 0, 90, 42) },
    { pane_id: "bottom", rect: rect(90, 42, 90, 18) },
  ],
};
assert.deepEqual(planBalance(stacked), [{ pane: "bottom", direction: "up", amount: 0.2 }]);

const lockRoot = mkdtempSync(join(tmpdir(), "pane-balance-test-"));
const withTab = (layout) => JSON.stringify({ result: { layout: { ...layout, tab_id: "w:t1" } } });

// Each resize is planned from a fresh layout, so the chain takes one resize per read.
const afterRoot = { ...chain, splits: [{ ...chain.splits[0], ratio: 0.75 }, ...chain.splits.slice(1)] };
const layouts = [chain, chain, afterRoot, balanced];
const calls = [];
await balanceTab("lead", {
  lockRoot,
  run: async (args) => {
    calls.push(args);
    return args[1] === "layout" ? withTab(layouts.shift()) : "{}";
  },
});
assert.deepEqual(calls.filter((args) => args[1] === "resize"), [
  ["pane", "resize", "--pane", "w2", "--direction", "right", "--amount", "0.25"],
  ["pane", "resize", "--pane", "w3", "--direction", "right", "--amount", "0.1667"],
]);
assert.equal(layouts.length, 0, "the layout is reread after every resize");

calls.length = 0;
await balanceTab("lead", { lockRoot, run: async (args) => (calls.push(args), withTab({ ...chain, zoomed: true })) });
assert.ok(calls.every((args) => args[1] === "layout"), "a zoomed tab is left alone");

// Two sessions balancing one tab take turns instead of applying the same delta twice.
let ratio = 0.75;
let resizes = 0;
const live = () => ({
  splits: [{ id: "split_0_root", direction: "right", ratio, rect: rect(0, 0, 180, 60) }],
  panes: [
    { pane_id: "lead", rect: rect(0, 0, 180 * ratio, 60) },
    { pane_id: "w1", rect: rect(180 * ratio, 0, 180 * (1 - ratio), 60) },
  ],
});
const shared = async (args) => {
  if (args[1] === "layout") return withTab(live());
  resizes++;
  await new Promise((resolve) => setTimeout(resolve, 20));
  const amount = Number(args[7]);
  ratio += args[5] === "right" ? amount : -amount;
  return "{}";
};
await Promise.all([balanceTab("lead", { lockRoot, run: shared }), balanceTab("w1", { lockRoot, run: shared })]);
assert.ok(Math.abs(ratio - 0.5) < 0.01, `concurrent sessions leave equal columns, got ${ratio}`);
assert.equal(resizes, 1, "the second session sees the balanced tab instead of overshooting it");

// A quitting Pi waits for its pane to close, then balances the tab it left through another pane.
const closing = (goneAfter) => {
  let gets = 0;
  const laidOut = [];
  const run = async (args) => {
    if (args[1] === "get") {
      if (gets++ < goneAfter) return JSON.stringify({ result: { pane: { pane_id: args[2], tab_id: "w:t1" } } });
      throw Object.assign(new Error("exit 1"), { stdout: '{"error":{"code":"pane_not_found"}}' });
    }
    if (args[1] === "list") {
      return JSON.stringify({ result: { panes: [{ pane_id: "x1", tab_id: "x:t1" }, { pane_id: "lead", tab_id: "w:t1" }] } });
    }
    if (args[1] === "layout") {
      laidOut.push(args[3]);
      return withTab(balanced);
    }
    throw new Error(`unexpected herdr call ${args.join(" ")}`);
  };
  return { run, laidOut };
};
const closed = closing(3);
await balanceAfterClose("w1", { run: closed.run, lockRoot, pollMs: 1, waitMs: 1000 });
assert.deepEqual(closed.laidOut, ["lead", "lead"], "the tab the pane left is balanced once it closes");

const kept = closing(Infinity);
await balanceAfterClose("w1", { run: kept.run, lockRoot, pollMs: 1, waitMs: 20 });
assert.deepEqual(kept.laidOut, [], "a pane that stays open after Pi quits changes nothing");

const spawned = [];
spawnAfterClose("w1", (command, args, options) => {
  spawned.push({ args, options });
  return { on() {}, unref() {} };
});
assert.match(spawned[0].args[0], /pi\/scripts\/pane-balance\.mjs$/);
assert.deepEqual(spawned[0].args.slice(1), ["after-close", "w1"]);
assert.equal(spawned[0].options.detached, true, "the helper outlives the quitting Pi");

const handlers = new Map();
const previous = process.env.HERDR_PANE_ID;
delete process.env.HERDR_PANE_ID;
paneBalance({ on(event, handler) { handlers.set(event, handler); } });
assert.equal(handlers.size, 0, "outside Herdr the extension registers nothing");
process.env.HERDR_PANE_ID = "lead";
paneBalance({ on(event, handler) { handlers.set(event, handler); } });
assert.deepEqual([...handlers.keys()].sort(), ["session_shutdown", "session_start"],
  "only a Pi starting or quitting rebalances; dispatch tools and results do not");
handlers.get("session_start")({ reason: "reload" });
handlers.get("session_shutdown")({ reason: "reload" });
if (previous === undefined) delete process.env.HERDR_PANE_ID;
else process.env.HERDR_PANE_ID = previous;

console.log("pi pane balance: pass");
