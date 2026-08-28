# Close the final review findings design

## Three acceptance points, not two

`choosing-graph` named `shipping-task` Task 6 and `boss-say` Task 7 as the two
places that discharge the adversarial-review obligation. But `boss-say` itself
already documents a third control-flow path: "close out `<task>`" for a single
dispatched instruction is a passthrough straight to `dispatching-work`'s own
Wrap-up branch, explicitly *not* Task 7 ("not this skill's Task 7, which is
about reporting a *batch* this skill itself started"). That branch's four steps
— confirm the instruction, close the pane, release locks, archive — never
mentioned the review.

The fix adds the review's disposition as a step in the Wrap-up branch itself,
guarded so it never re-runs work `shipping-task` Task 6 or `boss-say` Task 7
already did: "if this instruction landed an ordinary programming change and
neither ... already dispositioned its review." That guard is what keeps the set
closed without double-counting — `shipping-task` Task 6 still calls into this
same branch after doing its own disposition, so the branch has to recognize
that case and skip, not redo, the work. `choosing-graph` now names all three.

## A `work-on`-produced plan disciplines its review per task

`shipping-task` Task 6 was written entirely in one-agent lifecycle language
("Once the agent reports the lifecycle is complete") while `work-on:29` already
states that a multi-app/phase request runs as "separate per-app worktree/MR/review
cycles" through `shipping-task`. Nothing said whether Task 6's disposition step
runs once per task in that plan or once for the whole plan — both readings fit
the text as written, so a reader who reaches Task 6 while more than one task in
the plan is still open cannot tell from Task 6 alone whether this task's review
counts as reported or whether the whole plan does.

The fix is one sentence naming the frequency directly, plus the matching
acceptance line in Task 6's own Verification. No new mechanism — the wave
dispatch and per-task status reporting already exist in `dispatching-work`;
this only removes the ambiguity about how many times the disposition clause at
the end of Task 6 actually runs.

## `boss-say` confirms before it dispositions

`shipping-task` Task 6 confirms the merge or commit reference first, then
dispositions the review against *that confirmed reference*. `boss-say` Task 7
skipped the first half — it dispositioned "against the item's own commit
reference" without ever confirming what that reference actually is. Task 5
only counts in-flight tasks, refills the queue, and relays checkpoints; Task
7's own data source is the terminal status file's free-text `note`, which the
worker writes about itself and nothing else checks. The fix inserts the same
two-step order `shipping-task` already uses: confirm the item's own completed
reference from its terminal report, then discharge the review against that
confirmed reference.

## The review route list, narrowed to what each reader can do

The obligation bullet named two routes — "a fresh-context subagent, or a
coworker" — for every reader, including two who cannot take the second one. A
writable coworker's own contract bullet already says "complete this task
directly rather than coordinating another coworker" (coworker nesting stops at
one level, `docs/roles.md`), so the very next bullet offering it a coworker
route contradicts the one before it. `bringing-coworker` itself only runs "from
a dispatched worker's current Herdr tab" — a headless `claude-p` worker has no
tab, so the route does not exist for it either, even though the rendered
contract text is identical for both dispatch modes (`render_dispatch_contract`
takes no mode parameter, by the same design constraint the previous round
established for the missing-anchor fallback).

Two facts already true and already documented settle both cases without adding
a mode parameter or naming a transport in the bullet (which the existing test
for this bullet already forbids): whether this dispatch *is* a coworker
(`coworker_context`, already known to `render_dispatch_contract`) and whether
`bringing-coworker` requires a live pane to run from. The route list becomes
conditional on `coworker_context`: "a fresh-context subagent, or
bringing-coworker from an interactive Herdr tab" for a top-level dispatch, and
just "a fresh-context subagent" for a coworker's own contract, since a coworker
can never take the other route regardless of transport. Neither string names
`herdr-pane` or `claude-p` literally, so the existing "a standing rule cannot be
scoped to one transport" test keeps holding.

## The worker's own coordination-graph obligation, delivered

`docs/roles.md` already states it: "a dispatched agent states its own [graph]
for its own task." Every live pointer that told an agent to run `choosing-graph`
for this purpose, though, sat on coordinator-side task text (`dispatching-work`
Task 3, `boss-say` Task 1) — nothing a dispatched worker is required to read
ever carried it. This is the exact delivery-gap shape H originally named for
the adversarial-review obligation, recurring for a different rule: a rule
written correctly in the authority document with no carrier to the surface the
obligated party actually reads.

The fix mirrors the existing anchor-naming bullet's own pattern (stated, not
asked; points to the skill that holds the criterion rather than restating it) as
a new standing contract bullet: "State your own coordination graph for this
task before you start, through `choosing-graph`; the main agent already stated
its own when it dispatched you." It does not restate the tie-break criterion
itself — that stays in `choosing-graph` alone, so the single-source-of-truth
property this repo already keeps for the anchor split holds for the graph split
too.

As a second, smaller fix: `CONTEXT.md`'s `Coordination graph` glossary entry
said only "the coordinator states it," while its neighboring `Reality anchor`
entry states both halves. The entry now reads "the coordinator states it before
it dispatches; a dispatched agent states its own for its own task," matching
`docs/roles.md`'s own wording and its neighbor's shape.

## Test strategy

Every new assertion pins an exact string this round adds to a skill, `CONTEXT.md`,
or the generated contract, following the file's existing convention: text
constructed from module-level Python string literals for the contract (via
`render_dispatch_contract`), `normalized()` substring checks for prose. The
retargeted test (`test_every_path_that_lands_a_change_checks_the_review`) keeps
every substantive assertion it had and updates only the wording that changed.
