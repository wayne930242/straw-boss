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

/** Equalises a Herdr tab only when a Pi starts in it or quits out of it. */
export default function paneBalance(pi: ExtensionAPI): void {
  const paneId = process.env.HERDR_PANE_ID;
  if (!paneId) return;
  pi.on("session_start", (event) => {
    if (event.reason === "startup") balanceTab(paneId).catch(() => {});
  });
  pi.on("session_shutdown", (event) => {
    if (event.reason === "quit") spawnAfterClose(paneId);
  });
}
