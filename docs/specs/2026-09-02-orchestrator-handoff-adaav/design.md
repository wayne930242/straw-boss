# Design

## Smallest approach

- Put the ownership-transfer rule and silent ADAAV ordering in `docs/roles.md`.
- Keep the injected `i-am-orchestrator` addition to one compact paragraph; it
  points to established state instead of repeating it.
- Add one orchestration-handoff entry skill and one script that creates and
  labels an independent Herdr tab, starts its agent, delivers the bounded
  continuity payload, and verifies acceptance.
- Store only a short-lived handoff receipt needed for the acceptance handshake.
  It is not a dispatch instruction, worker status, or plan task.
- The receiving prompt names `boss-say` and the transferred scope. It establishes
  that route before the `boss-say` handoff branch records acceptance from the
  receiver's own `HERDR_PANE_ID` together with the established owner, graph,
  and reality anchor. The source validates those structured route facts. The
  acceptance script also matches its caller process ancestry to Herdr's live
  foreground process for that pane; its normal orchestrator stance owns routing
  from there.

## Failure and cleanup

The launcher binds the source argument to its current `HERDR_PANE_ID` and retries
prompt acceptance once. Until acceptance, the source is the owner. On final
failure it retries tab cleanup, interrupts and closes the receiver pane when
needed, and surfaces any remaining cleanup failure while keeping the source
pane. On success it returns the accepted identity; the source either continues
with explicit retained scope or closes its pane after the compact handoff report.

## Prompt budget

ADAAV is represented once as an ordering, not copied into each branch. The
continuity payload uses named fields with omitted empty values and never embeds a
transcript. Retained source work is carried as a receiver exclusion rather than
an extra continuity field. Handshake JSON uses atomic replacement. Tests compare
the generated payload against a fixed small budget and
reject required phase headings or duplicated authority prose.
