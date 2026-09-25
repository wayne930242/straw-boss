import assert from "node:assert/strict";
import paneBalance, { balanceTab, planBalance } from "../../pi/extensions/pane-balance.ts";

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

const calls = [];
await balanceTab("lead", async (args) => {
  calls.push(args);
  return args[1] === "layout" ? JSON.stringify({ result: { layout: chain } }) : "{}";
});
assert.deepEqual(calls.slice(1), [
  ["pane", "resize", "--pane", "w2", "--direction", "right", "--amount", "0.25"],
  ["pane", "resize", "--pane", "w3", "--direction", "right", "--amount", "0.1667"],
]);

calls.length = 0;
await balanceTab("lead", async (args) => {
  calls.push(args);
  return JSON.stringify({ result: { layout: { ...chain, zoomed: true } } });
});
assert.equal(calls.length, 1, "a zoomed tab is left alone");

const handlers = new Map();
const previous = process.env.HERDR_PANE_ID;
delete process.env.HERDR_PANE_ID;
paneBalance({ on(event, handler) { handlers.set(event, handler); } });
assert.equal(handlers.size, 0, "outside Herdr the extension registers nothing");
process.env.HERDR_PANE_ID = "lead";
paneBalance({ on(event, handler) { handlers.set(event, handler); } });
assert.deepEqual([...handlers.keys()].sort(), ["message_end", "session_shutdown", "tool_result"]);
handlers.get("session_shutdown")();
if (previous === undefined) delete process.env.HERDR_PANE_ID;
else process.env.HERDR_PANE_ID = previous;

console.log("pi pane balance: pass");
