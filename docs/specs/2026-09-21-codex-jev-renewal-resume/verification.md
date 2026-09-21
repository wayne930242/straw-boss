# Verification

Baseline: `7357114522ba56633f67658d61872b88cb4ab9ad` on `main`.
Runtime: Codex 0.155.1 and Herdr 0.9.0. Source-checkout hooks ran in an isolated
Codex home and a dedicated sibling pane. No global plugin installation changed.

Private evidence root:
`~/.straw-boss/evidence/codex-jev-renewal-resume/`.

| Requirement | Evidence | Result |
|---|---|---|
| Opt-in only, nonblank key, silent disabled path | Parameterized public Stop tests cover unset, empty and whitespace-only keys; ordinary renewal output has no Jev instruction and the Jev store remains absent. | pass |
| Codex 200k Stop threshold and existing loop guards | Exact 200000/200001 boundary and repeated-Stop tests; live source triggered at 226554 input tokens, captured in application-pane.txt. | pass |
| Shared live criteria/policy, locks, fitting, truncation | Equal-length distinct results produce distinct live requests; complete long-result chunk coverage and maximum-score aggregation tests; governing and recent pairs bypass judging. Existing Codex truncation/retention tests pass. Live application used 16 Jev requests and 402608 Jev input tokens, dropped eight completed log pairs and kept two recent pairs. | pass |
| Fresh replacement, preserved non-tool history and complete pairs | application-evidence.json: persisted replacement equals the archived candidate exactly; original source preserves the archived byte prefix. Existing pair/reasoning/image regressions remain green. | pass |
| Backend 10% gate with zero-cache proof | Successful run 9c64ef0ffd134d09b9087f2adb8984c3: baseline 227549, candidate 16093, both zero-cache; conservative live-input gate reduction 92.5867%. Cached, missing, failed and gate-miss cases select fallback in tests. | pass |
| Private lossless archive before application; separate actual observation | Original rollout text and complete candidate rows precede transport in runs/9c64ef0ffd134d09b9087f2adb8984c3.json; descriptor/symlink regressions pass. Probe credential cleanup is tested before launch and on spawn failure. application-evidence.json shows zero remaining probe auth copies. Actual resumed backend input was 19676 on the first request; a subsequent Stop persisted 19710 as the observed session input and application.status=verified. | pass |
| Same-pane codex resume and role/routing continuity | Pane w12:p9 and terminal term_65bf56d8c77c419 changed from source 0c202725-9f05-4727-8f6e-65210ab27297 to candidate dbffb870-2807-4e24-b6ee-aafc1f7dbffb. application-pane.txt records the socket client launch and JEV_CONTINUED with OAK-72. Existing role adoption tests cover main, worker and lineage behavior; the live probe uses standalone-worker. | pass |
| Gate/failure fallback | Initial native-compaction/unchanged-candidate run 61be70270c244c8b96a8d0ae62c68ebd completed ordinary renewal. Final invalid-key failure run ed526acf18a44b998984f9e1670a7bfb completed /clear, printed FALLBACK_CONTINUED with OAK-72 and observed 14086 input tokens in the fresh session. Corrupt request, failed-start restoration, record replacement and source-progress races have isolated regressions. | pass |
| Ordinary providers and activation baseline unchanged | Existing renewal suite remains green; source diff leaves ordinary Claude and disabled Codex selection unchanged. Activation and custom Codex configuration were confined to test launch processes and private fixtures. No startup-file/global-configuration edit. | pass |
| Solo-mode commit and authorization boundaries | The completed change-set is committed directly on main; the dispatch completion records its SHA and approve disposition. Version bump, push and installer have not run. | pass |
| Independent fresh-context review | Final independent rereview approved: F1/F2/F3 closed, Standards and Spec have no remaining blocking findings; reviewer ran 46 tests and 8 subtests. | pass |

## Validation status

- Final frozen-source repository run: 554 passed, 210 subtests passed (153.25 seconds).
- Initial pre-review run: 539 passed, 209 subtests passed (159.21 seconds).
- Vendor: 40 tests passed; npm build passed. npm ci preserved the lockfile.
- Final focused renewal regressions: 36 passed. The frozen-source full run above
  includes the combined source-advance and persistence-failure regressions.
- An earlier concurrent full run imported mixed pre/post-edit modules and failed
  three dynamic-import tests; its result is superseded by the frozen-source run.
- Independent initial review: Standards found no separate language/diff issue;
  Spec found two P1 issues (result-free scoring and outer fallback identity) and
  one P2 issue (credential cleanup). Final rereview closed all three and returned
  approve after 46 tests / 8 subtests (1.15 seconds) and diff checks. The final
  disposition is archived under `~/.straw-boss/dispatch/archive/` with the
  straw-boss--jev-renewal-review lifecycle artifacts.

The first large fixture triggered native compaction before delivery, proving the
ordinary fallback branch. The next provider turn stalled after its commentary;
the test driver interrupted it and submitted the exact renewal command. Thus the
live evidence proves the real 200k hook and the implemented renewal transaction,
with one explicit retry of the provider turn; it does not claim uninterrupted
provider execution for that attempt. A first transport attempt exposed empty
successful stdout from herdr pane run. The corrected adapter then completed the
same-pane swap; preserve the failed attempt as evidence rather than counting it
as success.

The live standalone test uses synthetic completed logs to establish mechanics,
not a forecast of savings in normal work. Model scores and resulting branches
can vary. Actual session usage is distinct from copied probe counts.

## Remaining observations

npm audit reports five pre-existing development-tool advisories: vitest critical,
vite high, and @vitest/mocker, esbuild, vite-node moderate. The exact report is in
the private evidence root. No dependency or lockfile upgrade is included.

Live role-adoption coverage in this run is standalone-worker; main/worker route
adoption is established by the existing executable tests, not a claimed live
multi-role deployment. The installed plugin remains unchanged.

## Reflexive pass

All friction notes in design.md are gaps. Missing optional project directories,
the unavailable graph tool, and the absent project model profile are
session/environment facts retained in the decision evidence; the existing
user-root model profile selected the review model. Scratch config, raw names and
ordinal issues are fixture corrections. Result-sensitive scoring, fallback
identity, credential cleanup and raw Herdr response handling are resolved by the
implementation and regression tests. These task-specific fixes require no new
universal agent rule or memory write.

Runtime and coworker panes were closed after evidence capture. The scratch home
authentication copy and test renewal checkpoint were removed; lossless private
evidence remains available.
