import { spawn } from "node:child_process";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { balanceTab } from "../scripts/pane-balance.mjs";

export { balanceAfterClose, balanceTab, planBalance } from "../scripts/pane-balance.mjs";

const HELPER = fileURLToPath(new URL("../scripts/pane-balance.mjs", import.meta.url));

/** Runs the helper outside this process, which exits before Herdr closes its pane. */
export function spawnAfterClose(paneId: string, tabId = process.env.HERDR_TAB_ID ?? "", launch = spawn): void {
  const runtime = /^(node|bun)(\.exe)?$/.test(basename(process.execPath)) ? process.execPath : "node";
  const child = launch(runtime, [HELPER, "after-close", paneId, tabId], { detached: true, stdio: "ignore" });
  child.on("error", () => {});
  child.unref();
}

// Survives /reload, which loads extensions again in the same process.
const STARTED = Symbol.for("straw-boss.pane-balance.started");

/** Equalises a Herdr tab only when a Pi starts in it or quits out of it. */
export default function paneBalance(pi: ExtensionAPI, balance = balanceTab): void {
  const paneId = process.env.HERDR_PANE_ID;
  if (!paneId) return;
  // Balance on load: session_start waits for every other extension's handler, about ten seconds later.
  const host = globalThis as { [STARTED]?: boolean };
  if (!host[STARTED]) {
    host[STARTED] = true;
    balance(paneId).catch(() => {});
  }
  pi.on("session_shutdown", (event) => {
    if (event.reason === "quit") spawnAfterClose(paneId);
  });
}
