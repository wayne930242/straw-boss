import { execFile } from "node:child_process";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type Rect = { x: number; y: number; width: number; height: number };
type Split = { id: string; direction: "right" | "down"; ratio: number; rect: Rect };
type Pane = { pane_id: string; rect: Rect };
export type Layout = { panes: Pane[]; splits: Split[]; zoomed?: boolean };
export type Resize = { pane: string; direction: "left" | "right" | "up" | "down"; amount: number };

// Herdr reports its split tree flat: `split_<depth>_<path>`, where the path spells the
// first (0) or second (1) child taken from the root, and the root's path is `root`.
const splitPath = (id: string): string => {
  const path = id.split("_").slice(2).join("_");
  return path === "root" ? "" : path;
};

const TOLERANCE = 0.01;
// A worker pane opens or closes shortly after the event that announces it.
const SETTLE_DELAYS_MS = [400, 1500];
// Tools that open a worker pane: a dispatch, a resumed dispatch, or dispatch-recovery's reattach and handoff.
const PANE_TOOLS = ["subagent", "subagent_resume", "dispatch_control"];

/** The resizes that give every leaf an equal share along each split's axis. */
export function planBalance(layout: Layout): Resize[] {
  const splits = new Map(layout.splits.map((split) => [splitPath(split.id), split]));
  const members = new Map<string, Pane[]>([["", layout.panes]]);
  const sides = (path: string): [Pane[], Pane[]] => {
    const split = splits.get(path)!;
    const horizontal = split.direction === "right";
    const boundary = horizontal
      ? split.rect.x + split.rect.width * split.ratio
      : split.rect.y + split.rect.height * split.ratio;
    const first: Pane[] = [];
    const second: Pane[] = [];
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
  const weight = (path: string, axis: Split["direction"]): number => {
    const split = splits.get(path);
    if (!split) return 1;
    const a = weight(`${path}0`, axis);
    const b = weight(`${path}1`, axis);
    return split.direction === axis ? a + b : Math.max(a, b);
  };
  const resizes: Resize[] = [];
  for (const [path, split] of [...splits].sort(([a], [b]) => a.length - b.length)) {
    const first = weight(`${path}0`, split.direction);
    const target = first / (first + weight(`${path}1`, split.direction));
    const delta = target - split.ratio;
    if (Math.abs(delta) < TOLERANCE) continue;
    const horizontal = split.direction === "right";
    const edge = (pane: Pane) => (horizontal ? pane.rect.x + pane.rect.width : pane.rect.y + pane.rect.height);
    const start = (pane: Pane) => (horizontal ? pane.rect.x : pane.rect.y);
    // Herdr moves the named edge of the pane: grow the first side from its far edge,
    // or grow the second side from its near edge.
    const pane = delta > 0
      ? members.get(`${path}0`)!.reduce((best, pane) => (edge(pane) > edge(best) ? pane : best))
      : members.get(`${path}1`)!.reduce((best, pane) => (start(pane) < start(best) ? pane : best));
    const direction = delta > 0 ? (horizontal ? "right" : "down") : (horizontal ? "left" : "up");
    resizes.push({ pane: pane.pane_id, direction, amount: Number(Math.abs(delta).toFixed(4)) });
  }
  return resizes;
}

const herdr = (args: string[]): Promise<string> =>
  new Promise((resolve, reject) => {
    execFile(process.env.HERDR_BIN_PATH || "herdr", args, { encoding: "utf8" }, (error, stdout) =>
      error ? reject(error) : resolve(stdout));
  });

export async function balanceTab(paneId: string, run = herdr): Promise<void> {
  const layout = JSON.parse(await run(["pane", "layout", "--pane", paneId])).result.layout as Layout;
  if (layout.zoomed) return;
  for (const resize of planBalance(layout)) {
    await run(["pane", "resize", "--pane", resize.pane, "--direction", resize.direction, "--amount", String(resize.amount)]);
  }
}

export default function paneBalance(pi: ExtensionAPI): void {
  const paneId = process.env.HERDR_PANE_ID;
  if (!paneId) return;
  const timers = new Set<ReturnType<typeof setTimeout>>();
  const schedule = (): void => {
    for (const delay of SETTLE_DELAYS_MS) {
      const timer = setTimeout(() => {
        timers.delete(timer);
        balanceTab(paneId).catch(() => {});
      }, delay);
      timers.add(timer);
    }
  };

  // Only the dispatching session sees these, so worker sessions never rebalance the tab.
  pi.on("tool_result", (event) => {
    if (PANE_TOOLS.includes(event.toolName) && !event.isError) schedule();
  });
  pi.on("message_end", (event) => {
    const message = event.message as { role?: string; customType?: string };
    if (message.role === "custom" && ["subagent_result", "subagent_stop"].includes(message.customType ?? "")) schedule();
  });
  pi.on("session_shutdown", () => {
    for (const timer of timers) clearTimeout(timer);
    timers.clear();
  });
}
