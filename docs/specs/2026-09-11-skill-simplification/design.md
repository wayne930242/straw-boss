# Design

Keep all 15 entrypoints. Rewrite the overloaded skills around their inputs, decisions, handoffs, and result. Preserve the compact messaging and coworker entrypoints where their callers differ.

`boss-say` owns both independent batches and dependency plans, using one capped scheduler. It calls `shipping-task` for each source-changing item's git lifecycle and `dispatching-work` for dispatch operations. Plan mechanics documents schemas, queries, and continuation; it links back to the scheduler and cleanup owners.

`dispatching-work` owns the brief and wrap-up procedure. All close-out paths reach it. `choosing-graph` owns the single review checkpoint; cleanup checks its result before archiving. CLI syntax and failure details stay in references, without duplicating executable internals.

Initialization loads app instructions for bounded inline discovery; a separate app workroom uses the normal dispatch readiness path. Existing confirmations are carried forward. Bootstrap retains evidence-backed optional artifacts and delegates source changes to `leveraging-tasks` when available.

Verification updates prose assertions only where this approved contract changes their owner or wording. Runtime lifecycle tests remain intact. Review named links and representative single-task, batch, init, recovery, and handoff routes after tests.
