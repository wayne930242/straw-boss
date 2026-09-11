from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalized(path: Path) -> str:
    return " ".join(path.read_text().replace("`", "").split())


def sentences(text: str) -> list[str]:
    collapsed = " ".join(text.replace("`", "").split())
    return [part.strip() for part in re.split(r"(?<=[.;])\s+", collapsed) if part.strip()]


def paragraphs(text: str) -> list[str]:
    """Instruction prose only -- YAML frontmatter is trigger metadata, not a
    statement of who decides what."""
    body = text
    if body.startswith("---"):
        body = body.partition("---\n")[2].partition("---\n")[2]
    blocks = re.split(r"\n\s*\n", body.replace("`", ""))
    return [" ".join(block.split()) for block in blocks if block.strip()]


def instruction_lines(path: Path) -> list[tuple[int, str]]:
    """Numbered lines a reader takes as instruction.

    `CONTEXT.md`'s Language section records retired terms on `_Avoid_:` lines
    on purpose, so a stale-vocabulary scan has to skip them or the glossary
    can never name what it retires.
    """
    return [
        (number, line)
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if not line.startswith("_Avoid_:")
    ]


def prose_surfaces(include_scripts: bool = False) -> list[Path]:
    """Live instruction surfaces -- what an agent actually reads to act.

    `docs` is deliberately non-recursive: only its top-level files are live
    instruction surfaces.
    """
    paths = [
        *(ROOT / "skills").glob("**/*.md"),
        *(ROOT / "docs").glob("*.md"),
        ROOT / "CONTEXT.md",
        ROOT / "README.md",
        ROOT / "README.zh-TW.md",
    ]
    if include_scripts:
        paths += sorted((ROOT / "scripts").glob("*.py"))
    return sorted(paths)



def contract_bullets(contract: str) -> list[str]:
    """The generated contract's top-level bullets, one string each.

    A rule's scope in this file is positional: a sentence inside the bullet
    that opens "In `herdr-pane`" is scoped to that mode, and the same sentence
    in its own bullet is not.
    """
    return [
        " ".join(block.replace("`", "").split())
        for block in re.split(r"\n- ", contract)[1:]
    ]



class SkillInstructionQualityTests(unittest.TestCase):
    def test_skills_have_no_defensive_red_flags_sections(self) -> None:
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted((ROOT / "skills").glob("*/SKILL.md"))
            if "## Red Flags" in path.read_text()
        ]
        self.assertEqual(offenders, [])

    def test_skills_have_no_quoted_hypothetical_defense_bullets(self) -> None:
        offenders: list[str] = []
        pattern = re.compile(r'^\s*-\s+["“][^"”]+["”]\s*[—-]', re.MULTILINE)
        for path in sorted((ROOT / "skills").glob("**/*.md")):
            if pattern.search(path.read_text()):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_init_and_work_on_use_the_shared_config_handler(self) -> None:
        for name in ("init", "work-on"):
            source = normalized(ROOT / "skills" / name / "SKILL.md")
            self.assertIn("shared read handler", source)
        schema = normalized(ROOT / "skills/init/references/apps-config-schema.md")
        self.assertIn("read-apps-config.py", schema)
        self.assertIn("exit 3", schema)
        self.assertIn("exit 1", schema)

    def test_live_skills_support_only_herdr_dispatch(self) -> None:
        for path in prose_surfaces():
            source = path.read_text().lower()
            self.assertNotIn("headless", source, str(path))
            self.assertNotIn("claude-p", source, str(path))
        self.assertIn("required for dispatch", (ROOT / "README.md").read_text())
        self.assertIn("委派必要需求", (ROOT / "README.zh-TW.md").read_text())
        self.assertFalse((ROOT / "scripts/run-headless-dispatched-agent.py").exists())

    def test_moving_base_refresh_is_conditional(self) -> None:
        source = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "plan-mechanics.md"
        )
        self.assertIn(
            "When parallel tasks target the same moving base or the remote base advanced",
            source,
        )
        self.assertNotIn("Every full-flow dispatch instruction in a plan/batch MUST", source)

    def test_local_files_fail_before_dispatch_unless_explicitly_optional(self) -> None:
        init_source = normalized(ROOT / "skills" / "init" / "SKILL.md")
        schema = normalized(
            ROOT / "skills" / "init" / "references" / "apps-config-schema.md"
        )
        mechanics = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "plan-mechanics.md"
        )

        self.assertIn("optional: true only when the app remains operable", init_source)
        self.assertIn("optional (boolean, default false", schema)
        self.assertIn("A missing entry is an error by default", mechanics)
        self.assertIn("stop before launching the worker", mechanics)
        self.assertIn("only when that exact entry has optional: true", mechanics)

    def test_skills_carry_their_own_rules_rather_than_pointing_at_a_document(
        self,
    ) -> None:
        offenders = [
            str(path.relative_to(ROOT))
            for path in sorted((ROOT / "skills").rglob("*.md"))
            if "roles.md" in path.read_text()
        ]
        self.assertEqual(offenders, [])

    def test_the_english_surface_is_written_in_english(self) -> None:
        surfaces = [
            *sorted((ROOT / "skills").rglob("*.md")),
            *sorted((ROOT / "docs").rglob("*.md")),
            ROOT / "README.md",
            ROOT / "CONTEXT.md",
        ]
        language_switcher = "](./README.zh-TW.md)"
        offenders = []
        for path in surfaces:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if language_switcher in line:
                    continue
                if any("\u4e00" <= character <= "\u9fff" for character in line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(offenders, [])

    def test_session_start_stance_states_each_coordination_rule_once(self) -> None:
        # The SessionStart hook injects the body only, so judge the body only.
        source = (ROOT / "skills" / "i-am-orchestrator" / "SKILL.md").read_text()
        _, _, body_source = source.partition("---\n")
        _, _, body_source = body_source.partition("---\n")
        stance = " ".join(body_source.replace("`", "").split())

        # Each rule is stated where it is operable, and nowhere else. The
        # injected stance previously restated work-content ownership, conflict
        # handling, and cleanup authority across four sections.
        for phrase in (
            "specification, design, implementation, and the verification method",
            "awaiting-main-agent",
            "conflict",
            "authorization",
            "peeking-work",
        ):
            self.assertEqual(stance.count(phrase), 1, phrase)

        # Worker-side mechanism a main agent never executes.
        self.assertNotIn("persists the state first and then notifies", stance)

        # Positive, direct phrasing throughout the compact stance.
        body = stance
        for defensive in (" do not ", " never ", " without asking ", ", not "):
            self.assertNotIn(defensive, body)

    def test_shipping_sync_is_conditional_and_scope_is_local(self) -> None:
        source = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("If the primary checkout tracks the merged base", source)
        self.assertNotIn("once the worktree is removed, sync the app's primary checkout too", source)
        self.assertNotIn("This finding needs DB/infra access I don't have", source)

    def test_every_grant_of_the_verification_method_is_scoped_to_the_anchor(
        self,
    ) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from straw_boss.dispatch import state as dispatch_state
        finally:
            sys.path.pop(0)

        surfaces = {
            "generated contract": dispatch_state.render_dispatch_contract(
                instruction_path=Path("/home/boss/.straw-boss/dispatch/app--slug.json"),
            ),
        }
        for path in prose_surfaces():
            surfaces[path.relative_to(ROOT).as_posix()] = path.read_text()

        unscoped = [
            f"{name}: {sentence}"
            for name, text in surfaces.items()
            for sentence in sentences(text)
            if "verification method" in sentence.lower()
            and "anchor" not in sentence.lower()
        ]
        self.assertEqual(unscoped, [])

    def test_graph_names_are_the_same_three_on_every_surface_that_lists_them(
        self,
    ) -> None:
        # The zh-TW README localizes the middle name; the other two are
        # identifiers and stay verbatim everywhere.
        graphs = (
            ("single-loop",),
            ("sub-agent fan-out/fan-in", "sub-agent 扇出／扇入"),
            ("orchestrator-worker",),
        )

        def named(text: str) -> int:
            return sum(any(form in text for form in graph) for graph in graphs)

        listing = [path for path in prose_surfaces() if named(path.read_text()) >= 2]
        self.assertNotEqual(listing, [], "no surface enumerates the graphs")
        incomplete = [
            path.relative_to(ROOT).as_posix()
            for path in listing
            if named(path.read_text()) != len(graphs)
        ]
        self.assertEqual(incomplete, [])

        stale = re.compile(r"supervisor-worker|coordinator's shape alone")
        self.assertEqual(
            [
                f"{path.relative_to(ROOT).as_posix()}:{number}"
                for path in prose_surfaces()
                for number, line in instruction_lines(path)
                if stale.search(line)
            ],
            [],
        )

    def test_the_claim_port_command_is_written_out_exactly_once(self) -> None:
        holders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted((ROOT / "skills").glob("**/*.md"))
            if "claim-resource.py\" claim-port" in path.read_text()
            or "claim-resource.py claim-port" in path.read_text()
        ]
        self.assertEqual(
            holders,
            ["skills/dispatching-work/references/shared-resource-coordination.md"],
        )

    def test_no_surface_gives_the_worker_the_anchor_category(self) -> None:
        # The worker has to be the subject, so the decision verb is required to
        # follow it -- otherwise every correct sentence that merely mentions a
        # worker somewhere reads as a violation.
        takes_the_category = re.compile(
            r"\b(?:worker|dispatched agent|coworker)\b[^.;]{0,60}?"
            r"\b(?:choose|chooses|choosing|pick|picks|picking|decide|decides|deciding"
            r"|select|selects|fix|fixes|name|names|settle|settles)\s+"
            r"(?:its own\s+|their own\s+|the\s+|a\s+|an\s+|which\s+)?"
            r"(?:reality\s+)?anchor\b",
            re.IGNORECASE,
        )
        offenders = [
            f"{path.relative_to(ROOT).as_posix()}: {sentence}"
            for path in prose_surfaces()
            for sentence in sentences(path.read_text())
            if takes_the_category.search(sentence)
        ]
        self.assertEqual(offenders, [])
        # And the check is live: the sentence it exists to reject is rejected.
        self.assertRegex(
            "The worker chooses the reality anchor and the method inside it.",
            takes_the_category,
        )

    def test_no_retired_coordination_alias_is_live_in_the_skills(self) -> None:
        headwords: list[str] = []
        retired: dict[str, list[str]] = {}
        term: str | None = None
        for line in (ROOT / "CONTEXT.md").read_text().splitlines():
            headword = re.fullmatch(r"\*\*(.+?)\*\*:", line.strip())
            if headword:
                term = headword.group(1)
                headwords.append(term)
            elif line.startswith("_Avoid_:") and term:
                retired[term] = [
                    alias.strip().lower()
                    for alias in line.partition(":")[2].split(",")
                    if alias.strip()
                ]

        coordination = ("Coordination graph", "Reality anchor", "Team-mode / solo-mode")
        self.assertEqual(
            sorted(term for term in retired if term in coordination),
            sorted(coordination),
        )
        # The batching decision is its own concept and keeps its own entry, so
        # the collision cannot come back as an unregistered term.
        self.assertIn("Dispatch shape", headwords)

        aliases = [alias for term in coordination for alias in retired[term]]
        live = [
            f"{path.relative_to(ROOT).as_posix()}:{number} {alias}"
            for path in sorted((ROOT / "skills").glob("**/*.md"))
            for number, line in instruction_lines(path)
            for alias in aliases
            if alias in line.lower()
        ]
        self.assertEqual(live, [])

    def test_lifecycle_mode_names_are_consistent_across_every_live_surface(self) -> None:
        stale = re.compile(r"full[ -]flow|light[ -]flow", re.IGNORECASE)
        offenders = [
            f"{path.relative_to(ROOT).as_posix()}:{number}"
            for path in prose_surfaces(include_scripts=True)
            for number, line in instruction_lines(path)
            if stale.search(line)
        ]
        self.assertEqual(offenders, [])

    def test_the_contract_carries_the_same_rules_to_every_agent_kind(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from straw_boss.dispatch import state as dispatch_state
        finally:
            sys.path.pop(0)

        path = Path("/home/boss/.straw-boss/dispatch/app--slug.json")
        for kind in ("claude", "codex"):
            contract = dispatch_state.render_dispatch_contract(path, agent_kind=kind)
            # The anchor arrives with the dispatch; the worker settles one only
            # for a dispatch that named none.
            self.assertIn("the reality anchor this dispatch names", contract)
            self.assertIn("settling the anchor yourselves when it names none", contract)
            self.assertIn("awaiting-main-agent", contract)
            with self.assertRaises(ValueError):
                dispatch_state.render_dispatch_contract(path, mode="claude-p", agent_kind=kind)

    def test_the_coordination_graph_is_stated_by_the_coordinator_alone(self) -> None:
        # The dispatched-agent contract asks a worker for no graph of its own,
        # so no surface may claim one is stated.
        context = normalized(ROOT / "CONTEXT.md")
        self.assertIn("The coordinator states it before it dispatches", context)
        for path in prose_surfaces():
            with self.subTest(surface=path.relative_to(ROOT).as_posix()):
                self.assertNotIn("states its own", normalized(path))

    def test_skill_names_and_metadata_remain_discoverable(self) -> None:
        expected = {
            "asking-peer-agents", "boss-assistant", "boss-say", "bringing-coworker",
            "choosing-graph", "contacting-orchestrators", "create-great-harness",
            "dispatching-work", "handoff-orchestrator", "i-am-orchestrator", "init",
            "notifying-main-agent", "peeking-work", "reporting-to-user",
            "shipping-task", "work-on",
        }
        paths = list((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual({p.parent.name for p in paths}, expected)
        for path in paths:
            with self.subTest(skill=path.parent.name):
                self.assertRegex(path.read_text(), rf"^---\nname: {path.parent.name}\ndescription: .+\n---")

    def test_local_skill_links_resolve_files_and_named_sections(self) -> None:
        for path in (ROOT / "skills").rglob("*.md"):
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
                if "://" in target:
                    continue
                file, _, anchor = target.partition("#")
                dest = (path.parent / file).resolve() if file else path
                with self.subTest(source=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue(dest.is_file(), target)
                    if anchor and dest.is_file():
                        headings = re.findall(r"^#{1,6} (.+)$", dest.read_text(), re.M)
                        slugs = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings}
                        self.assertIn(anchor, slugs)

    def test_cross_skill_references_use_named_sections(self) -> None:
        for path in (ROOT / "skills").rglob("*.md"):
            self.assertNotRegex(path.read_text(), r"(?:Task|Step) \d+['’]s", str(path))
        work_on = normalized(ROOT / "skills/work-on/SKILL.md")
        self.assertIn("this skill only resolves targets", work_on)
        self.assertNotIn("Write ~/.straw-boss/plans", work_on)
        self.assertIn("../boss-say/SKILL.md#plan-and-schedule", work_on)

    def test_graph_precedence_and_anchor_categories_have_one_owner(self) -> None:
        graph = (ROOT / "skills/choosing-graph/SKILL.md").read_text()
        section = graph.partition("## Coordination graphs")[2].partition("## Reality anchors")[0]
        self.assertIn("first matching case", section)
        self.assertEqual(re.findall(r"^- \*\*([^*]+)\*\*", section, re.M),
                         ["orchestrator-worker", "sub-agent fan-out/fan-in", "single-loop"])
        self.assertIn("independent review is a checkpoint", section)
        self.assertIn("Only `orchestrator-worker` writes", section)
        anchors = graph.partition("## Reality anchors")[2].partition("## Review checkpoint")[0]
        self.assertEqual(re.findall(r"^- \*\*([^*]+)\*\*", anchors, re.M),
                         ["testing", "pseudo-human", "human", "adversarial-review"])
        self.assertIn("The main agent names the anchor and checkpoint", anchors)
        self.assertIn("verification method inside that anchor", anchors)
        self.assertIn("evidence references", anchors)
        for name in ("boss-say", "dispatching-work"):
            source = (ROOT / "skills" / name / "SKILL.md").read_text()
            self.assertIn("../choosing-graph/SKILL.md", source)
            self.assertNotIn("## Reality anchors", source)

    def test_init_reuses_choices_and_checks_readiness_before_optional_dispatch(self) -> None:
        source = normalized(ROOT / "skills/init/SKILL.md")
        self.assertIn("Reuse confirmed app and routing choices", source)
        self.assertIn("load the target app's instructions and inspect it directly", source)
        self.assertIn("dispatch readiness](#check-dispatch-readiness) before launching", source)
        self.assertIn("instruction sync can finish without Herdr", source)
        self.assertIn("before editing the same files", source)
        self.assertIn("surrounding content must be preserved", source)
        self.assertNotIn("For every confirmed app, dispatch", source)

    def test_batch_has_one_scheduler_and_queries_slots_not_queue_size(self) -> None:
        boss = normalized(ROOT / "skills/boss-say/SKILL.md")
        mechanics = normalized(ROOT / "skills/dispatching-work/references/plan-mechanics.md")
        self.assertIn("owns task decomposition, dependency edges, and scheduling", boss)
        self.assertIn("cap - in-flight", boss)
        self.assertIn("--ready", boss)
        self.assertIn("Pending user checkpoints still hold slots", boss)
        self.assertIn("only done satisfies a dependency", boss)
        self.assertIn("#plan-and-schedule", mechanics)
        self.assertNotIn("dispatch every", mechanics)
        self.assertNotIn("plan-confirmation decision", boss)
        self.assertIn("Reuse the user's specified tasks and decisions", boss)

    def test_event_and_peek_routes_preserve_quiet_waiting(self) -> None:
        boss = normalized(ROOT / "skills/boss-say/SKILL.md")
        dispatch = normalized(ROOT / "skills/dispatching-work/SKILL.md")
        peek = normalized(ROOT / "skills/peeking-work/SKILL.md")
        self.assertIn("when the user asks or observed evidence disagrees", boss)
        self.assertIn("Unchanged waiting stays quiet", boss)
        self.assertIn("Persisted status drives the lifecycle", dispatch)
        self.assertIn("retain the task and its slot", dispatch)
        self.assertIn("slot accounting and task status stay as recorded", dispatch)
        self.assertLess(peek.index("status and the recent entries"), peek.index("herdr agent read"))
        self.assertIn("If these answer the question, report that result", peek)
        self.assertIn("../dispatching-work/SKILL.md#handle-events", peek)

    def test_every_cleanup_route_reaches_one_wrap_up_owner(self) -> None:
        paths = ["boss-say/SKILL.md", "shipping-task/SKILL.md", "bringing-coworker/SKILL.md",
                 "dispatching-work/references/plan-mechanics.md"]
        for path in paths:
            source = (ROOT / "skills" / path).read_text()
            self.assertIn("SKILL.md#wrap-up", source, path)
            self.assertNotIn("scripts/wrap-up-task.py", source, path)
        dispatch = normalized(ROOT / "skills/dispatching-work/SKILL.md")
        self.assertLess(dispatch.index("review checkpoint"), dispatch.index("wrap-up-task.py"))
        self.assertLess(dispatch.index("Release every remaining lock"), dispatch.index("wrap-up-task.py"))
        self.assertIn("same-task continuation", dispatch)
        self.assertIn("Require terminal status", dispatch)
        self.assertIn("pending instruction that never launched", dispatch)
        self.assertIn("coordinator pane and shared tab remain open", dispatch)

    def test_review_policy_reuses_disposition_for_the_completed_change(self) -> None:
        graph = normalized(ROOT / "skills/choosing-graph/SKILL.md")
        self.assertIn("Review one coherent programming change-set once", graph)
        self.assertIn("fresh-context reviewer examines the finished change-set directly", graph)
        self.assertIn("confirms the completion reference", graph)
        self.assertIn("Reuse an existing disposition for the same change-set", graph)
        self.assertIn("unresolved findings reopen", graph)
        shipping = normalized(ROOT / "skills/shipping-task/SKILL.md")
        self.assertIn("For each completed task", shipping)
        self.assertIn("current-agent task applies that checkpoint here", shipping)

    def test_recovery_and_lock_contracts_survive_simplification(self) -> None:
        mechanics = normalized(ROOT / "skills/dispatching-work/references/dispatch-mechanics.md")
        shared = normalized(ROOT / "skills/dispatching-work/references/shared-resource-coordination.md")
        self.assertIn("pane closure alone establishes only reachability", mechanics)
        self.assertIn("refuses a reachable worker or an existing terminal status", mechanics)
        self.assertIn("both the main agent's dispatch-time port claim and any worker-held lock", shared)
        self.assertIn("done, failed, and cancelled", shared)
        self.assertIn("before archiving", shared)
        self.assertIn("expiry alone does not establish that its process stopped", shared)
        self.assertIn("one user account on one machine", shared)

    def test_mode_and_authorization_reuse_existing_user_direction(self) -> None:
        shipping = normalized(ROOT / "skills/shipping-task/SKILL.md")
        self.assertIn("Reuse the user's established mode and base branch", shipping)
        self.assertIn("forbidDirectCommit: true selects team-mode automatically", shipping)
        self.assertIn("For a batch, ask once", shipping)
        self.assertIn("reserve it for one task at a time", shipping)
        self.assertIn("Merge and pushes to another tracked branch require user authorization", shipping)
        self.assertIn("worker asks in its own pane", shipping)

    def test_harness_reuses_authorization_and_limits_optional_artifacts(self) -> None:
        source = normalized(ROOT / "skills/create-great-harness/SKILL.md")
        self.assertIn("Reuse authorization from the user request or dispatch instruction", source)
        self.assertIn("concrete project evidence and authorization covering that addition", source)
        self.assertIn("both a blocking input and an allowed input", source)
        self.assertIn("verify the provider's current skill and rule specifications", source)
        self.assertIn("leveraging-tasks", source)
        self.assertNotIn("there's no user in this session", source)

    def test_handoff_routes_before_accepting_with_existing_approval(self) -> None:
        source = normalized(ROOT / "skills/boss-say/SKILL.md")
        self.assertLess(source.index("owner, graph, and anchor are established"),
                        source.index("accept-orchestrator-handoff.py"))
        for flag in ("--owner", "--coordination-graph", "--reality-anchor"):
            self.assertIn(flag, source)
        self.assertIn("existing approval and scope exclusions", source)
        handoff = normalized(ROOT / "skills/handoff-orchestrator/SKILL.md")
        self.assertIn("A new tab is created only after the user approves", handoff)
        self.assertIn("ownership remains here", handoff)

    def test_preflight_requires_both_integration_and_scheduling_need(self) -> None:
        source = normalized(ROOT / "skills/boss-say/SKILL.md")
        self.assertIn("Keep diagnosis and repair in the same worker", source)
        self.assertIn("only when the failure crosses an integration boundary and its explanation is needed to shape or schedule later dispatches", source)
        self.assertIn("choosing-graph for the explanation's review or the fix's testing checkpoint", source)

    def test_boss_assistant_hands_source_repair_to_development_owner(self) -> None:
        source = normalized(ROOT / "skills/boss-assistant/SKILL.md")
        self.assertIn("leveraging-tasks, which owns design, implementation, and verification", source)
        self.assertIn("relevant baseline", source)
        self.assertIn("actual UAT outcome", source)
        self.assertIn("user's publication decision", source)

    def test_the_close_out_report_grades_findings_and_routes_the_follow_up(
        self,
    ) -> None:
        source = normalized(ROOT / "skills/reporting-to-user/SKILL.md")
        self.assertIn("Report Alert, then Warn, then Info, then Next", source)
        self.assertIn("Number the items inside each level from 1", source)
        self.assertIn("cites the findings it answers as (Alert 1) or (Warn 2)", source)
        self.assertIn("Every item is one line", source)
        self.assertIn("the only level that asks the user anything", source)
        self.assertIn("Alert-derived items first, then Warn-derived", source)
        self.assertIn("harness-native ask-question interface", source)
        self.assertIn(
            "Present one item at a time in Next order, wait for each answer, "
            "and collect the answers until every item has one",
            source,
        )
        self.assertIn("A declined item is recorded with the user's decision", source)
        self.assertIn("The accepted items enter", source)
        self.assertIn("together as one round", source)
        self.assertIn("../boss-say/SKILL.md#route-the-work", source)
        # The close-out has one owner, reached from the entry point and the
        # injected stance.
        self.assertIn(
            "reporting-to-user", normalized(ROOT / "skills/boss-say/SKILL.md")
        )
        self.assertIn(
            "reporting-to-user",
            normalized(ROOT / "skills/i-am-orchestrator/SKILL.md"),
        )


if __name__ == "__main__":
    unittest.main()
