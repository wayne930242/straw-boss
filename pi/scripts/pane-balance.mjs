// Equalises the panes of one Herdr tab. The Pi extension imports it when its pane opens,
// and runs it detached as `pane-balance.mjs after-close <pane> <tab>` when its Pi quits, because
// the pane closes only after the Pi process is gone.
import { execFile } from "node:child_process";
import { mkdir, rmdir, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** @typedef {{ x: number, y: number, width: number, height: number }} Rect */
/** @typedef {{ id: string, direction: "right" | "down", ratio: number, rect: Rect }} Split */
/** @typedef {{ pane_id: string, rect: Rect }} Pane */
/** @typedef {{ panes: Pane[], splits: Split[], zoomed?: boolean }} Layout */
/** @typedef {{ pane: string, direction: "left" | "right" | "up" | "down", amount: number }} Resize */
/** @typedef {(args: string[]) => Promise<string>} Run */

const TOLERANCE = 0.01;
// Each pass applies one resize and rereads the layout; a tab never needs more passes than this.
const MAX_PASSES = 32;
const LOCK_ROOT = join(tmpdir(), "straw-boss-pane-balance");
const LOCK_WAIT_MS = 15_000;
const LOCK_STALE_MS = 30_000;
// pi-herdr-agents closes a worker's pane once its lead has taken the result.
const CLOSE_WAIT_MS = 30_000;
const POLL_MS = 250;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Herdr reports its split tree flat: `split_<depth>_<path>`, where the path spells the
// first (0) or second (1) child taken from the root, and the root's path is `root`.
const splitPath = (id) => {
  const path = id.split("_").slice(2).join("_");
  return path === "root" ? "" : path;
};

/**
 * The resizes that give every leaf an equal share along each split's axis, outermost first.
 * @param {Layout} layout
 * @returns {Resize[]}
 */
export function planBalance(layout) {
  const splits = new Map(layout.splits.map((split) => [splitPath(split.id), split]));
  /** @type {Map<string, Pane[]>} */
  const members = new Map([["", layout.panes]]);
  const sides = (path) => {
    const split = splits.get(path);
    const horizontal = split.direction === "right";
    const boundary = horizontal
      ? split.rect.x + split.rect.width * split.ratio
      : split.rect.y + split.rect.height * split.ratio;
    const first = [];
    const second = [];
    for (const pane of members.get(path) ?? []) {
      const centre = horizontal ? pane.rect.x + pane.rect.width / 2 : pane.rect.y + pane.rect.height / 2;
      (centre < boundary ? first : second).push(pane);
    }
    return [first, second];
  };
  for (const path of [...splits.keys()].sort((a, b) => a.length - b.length)) {
    const [first, second] = sides(path);
    members.set(`${path}0`, first);
    members.set(`${path}1`, second);
  }
  const weight = (path, axis) => {
    const split = splits.get(path);
    if (!split) return 1;
    const a = weight(`${path}0`, axis);
    const b = weight(`${path}1`, axis);
    return split.direction === axis ? a + b : Math.max(a, b);
  };
  /** @type {Resize[]} */
  const resizes = [];
  for (const [path, split] of [...splits].sort(([a], [b]) => a.length - b.length)) {
    const first = weight(`${path}0`, split.direction);
    const target = first / (first + weight(`${path}1`, split.direction));
    const delta = target - split.ratio;
    if (Math.abs(delta) < TOLERANCE) continue;
    const horizontal = split.direction === "right";
    const edge = (pane) => (horizontal ? pane.rect.x + pane.rect.width : pane.rect.y + pane.rect.height);
    const start = (pane) => (horizontal ? pane.rect.x : pane.rect.y);
    // Herdr moves the named edge of the pane: grow the first side from its far edge,
    // or grow the second side from its near edge.
    const pane = delta > 0
      ? members.get(`${path}0`).reduce((best, pane) => (edge(pane) > edge(best) ? pane : best))
      : members.get(`${path}1`).reduce((best, pane) => (start(pane) < start(best) ? pane : best));
    const direction = delta > 0 ? (horizontal ? "right" : "down") : (horizontal ? "left" : "up");
    resizes.push({ pane: pane.pane_id, direction, amount: Number(Math.abs(delta).toFixed(4)) });
  }
  return resizes;
}

/** @type {Run} */
export const herdr = (args) =>
  new Promise((resolve, reject) => {
    execFile(process.env.HERDR_BIN_PATH || "herdr", args, { encoding: "utf8" }, (error, stdout, stderr) =>
      error ? reject(Object.assign(error, { stderr })) : resolve(stdout));
  });

const readLayout = async (paneId, run) =>
  /** @type {Layout & { tab_id: string }} */ (JSON.parse(await run(["pane", "layout", "--pane", paneId])).result.layout);

/** Holds a per-tab directory lock so concurrent Pi sessions take turns resizing one tab. */
async function withTabLock(tabId, lockRoot, work) {
  const lock = join(lockRoot, tabId.replace(/[^\w.-]/g, "_"));
  await mkdir(lockRoot, { recursive: true });
  const deadline = Date.now() + LOCK_WAIT_MS;
  for (;;) {
    try {
      await mkdir(lock);
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      const age = await stat(lock).then((info) => Date.now() - info.mtimeMs, () => 0);
      if (age > LOCK_STALE_MS) {
        await rmdir(lock).catch(() => {});
        continue;
      }
      if (Date.now() > deadline) return;
      await sleep(100);
    }
  }
  try {
    await work();
  } finally {
    await rmdir(lock).catch(() => {});
  }
}

/**
 * Equalises the tab holding `paneId`. Every resize is planned from a freshly read layout,
 * so a pane that opens or closes mid-way is accounted for instead of overshot.
 * @param {string} paneId
 * @param {{ run?: Run, lockRoot?: string }} [options]
 */
export async function balanceTab(paneId, { run = herdr, lockRoot = LOCK_ROOT } = {}) {
  const { tab_id: tabId } = await readLayout(paneId, run);
  await withTabLock(tabId, lockRoot, async () => {
    for (let pass = 0; pass < MAX_PASSES; pass++) {
      const layout = await readLayout(paneId, run);
      if (layout.zoomed) return;
      const [resize] = planBalance(layout);
      if (!resize) return;
      await run(["pane", "resize", "--pane", resize.pane, "--direction", resize.direction, "--amount", String(resize.amount)]);
    }
  });
}

/** Whether Herdr still has the pane; `undefined` when Herdr could not answer. */
async function paneTab(paneId, run) {
  try {
    return /** @type {string} */ (JSON.parse(await run(["pane", "get", paneId])).result.pane.tab_id);
  } catch (error) {
    // Herdr reports a missing pane on stderr.
    if (String(error?.stderr ?? "").includes("pane_not_found")) return null;
    return undefined;
  }
}

/**
 * Waits for `paneId` to close, then equalises the tab it left. The pane may already be gone
 * when this starts, so `knownTab` names the tab the Pi last saw. A pane that outlives its
 * Pi, such as a shell the user keeps, changes no layout and is left alone.
 * @param {string} paneId
 * @param {string | undefined} knownTab
 * @param {{ run?: Run, lockRoot?: string, pollMs?: number, waitMs?: number }} [options]
 */
export async function balanceAfterClose(paneId, knownTab, { run = herdr, lockRoot = LOCK_ROOT, pollMs = POLL_MS, waitMs = CLOSE_WAIT_MS } = {}) {
  let current = await paneTab(paneId, run);
  const tabId = current || knownTab;
  if (!tabId) return;
  const deadline = Date.now() + waitMs;
  while (current !== null) {
    if (Date.now() > deadline) return;
    await sleep(pollMs);
    current = await paneTab(paneId, run);
  }
  const panes = /** @type {{ pane_id: string, tab_id: string }[]} */ (JSON.parse(await run(["pane", "list"])).result.panes);
  const anchor = panes.find((pane) => pane.tab_id === tabId);
  if (anchor) await balanceTab(anchor.pane_id, { run, lockRoot });
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv[2] === "after-close" && process.argv[3]) {
  await balanceAfterClose(process.argv[3], process.argv[4]).catch(() => {});
}
