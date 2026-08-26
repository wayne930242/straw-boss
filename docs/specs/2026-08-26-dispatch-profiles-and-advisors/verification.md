# Dispatch profiles and advisors verification

## Scope and environment

- Scope: init work routes, instruction profile/advisor fields, Claude/Codex
  provider argument application, dispatch-brief boundaries, and dispatched
  evidence-bearing managed-app research.
- Branch: `main`.
- Environment: Linux/WSL, Python 3.13.13, OpenSpec 1.3.1.
- Date: 2026-08-26 (Asia/Taipei).

## Primary flows exercised

- Claude instruction records provider profile, model, effort, and native advisor;
  fake-Herdr argv receives `--agent`, `--model`, `--effort`, and `--advisor`
  exactly once.
- Codex instruction records profile, model, and effort; fake-Herdr argv receives
  `--profile`, `--model`, and `model_reasoning_effort` with no advisor.
- Codex advisor is refused before an instruction or worker pane is created.
- Raw provider options cannot override instruction-owned profile/model/effort or
  advisor values.
- Older instructions without `agent_profile` or `advisor_model` still launch.
- Init and dispatch source contracts use complete work routes and accurately
  distinguish Claude's native advisor from Codex's unsupported case.
- Dispatch, shipping, batch planning, role docs, and the immutable worker
  contract leave target-app context discovery to the worker.
- Managed-app investigation, audit, and diagnosis always dispatch; a confirmed
  lower-tier route is allowed, but every task asks for an explanatory conclusion
  with evidence references rather than a yes-or-no answer.

## Automated evidence

- `python3 -m unittest tests.test_dispatched_agent_lifecycle_transport`: 50 tests
  passed.
- `python3 -m unittest discover -s tests`: 65 tests passed.
- `python3 -m py_compile scripts/dispatch-task.py scripts/dispatch_state.py
  scripts/launch-dispatched-agent.py`: passed.
- `openspec validate --all --strict`: 8 passed, 0 failed.
- `git diff --check`: passed.

## QA findings

### Resolved

- `work-on` and `docs/architecture.md` still allowed a solo read against a
  managed app after the new context boundary was introduced. Reproduction was a
  targeted contradiction scan for `solo`, `answer inline`, and target-app read
  guidance. Root cause was duplicated, older execution-tier prose outside the
  initially edited specialist skills. Both now state that needing managed-app
  files makes dispatch mandatory; the focused and full suites passed afterward.

### Deferred

None. No unresolved finding contradicts the release criteria.
