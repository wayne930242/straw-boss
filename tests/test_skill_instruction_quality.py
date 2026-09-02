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

    `docs` is deliberately non-recursive. `docs/specs/` and `docs/adr/` are
    dated records of what one change decided and how it was verified; a
    superseded ADR keeps its era's wording on purpose, so scanning them for
    current vocabulary would report history as drift.
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

    def test_init_delegates_app_owned_reconnaissance(self) -> None:
        source = normalized(ROOT / "skills" / "init" / "SKILL.md")
        self.assertIn(
            "dispatch bounded reconnaissance rooted in each confirmed app",
            source,
        )
        self.assertIn("returns proposed fields with evidence references", source)
        self.assertNotIn("read each app's git log", source)
        self.assertNotIn("grep every app's skills", source)

    def test_harness_has_no_guessed_default_artifacts(self) -> None:
        source = normalized(ROOT / "skills" / "create-great-harness" / "SKILL.md")
        self.assertIn("CLAUDE.md is the only unconditional artifact", source)
        self.assertIn("concrete project evidence or explicit confirmed scope", source)
        self.assertNotIn("universally applicable", source)
        self.assertNotIn("single most common irreversible-mistake footgun", source)
        self.assertNotIn("Target under 100 lines", source)
        self.assertNotIn("Every app this bootstraps starts with zero skills", source)

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

    def test_batch_and_single_app_routing_have_bounded_scope(self) -> None:
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        work_on = normalized(ROOT / "skills" / "work-on" / "SKILL.md")
        self.assertIn("A batch may contain independent items", dispatching)
        self.assertNotIn("batch is one multi-app unit of work only", dispatching)
        self.assertIn("unless the request is explicitly outside that app", work_on)
        self.assertNotIn("every request resolves to it", work_on)

    def test_investigation_contract_is_positive_and_consistent(self) -> None:
        for skill_name in (
            "inspecting-app",
            "investigating-app",
            "troubleshooting-app",
        ):
            source = normalized(ROOT / "skills" / skill_name / "SKILL.md")
            self.assertIn("evidence references", source)
            self.assertNotIn("not a yes-or-no answer", source)
        troubleshooting = normalized(
            ROOT / "skills" / "troubleshooting-app" / "SKILL.md"
        )
        self.assertNotIn("from your own diagnosis", troubleshooting)
        lifecycle_tests = "\n".join(
            (ROOT / "tests" / name).read_text()
            for name in (
                "dispatched_agent_lifecycle_support.py",
                "test_dispatched_agent_lifecycle_contract.py",
                "test_dispatched_agent_naming_and_coworker.py",
                "test_dispatched_agent_launch_and_delivery.py",
                "test_dispatched_agent_status_and_recovery.py",
            )
        )
        self.assertNotIn("Do not investigate the target app to enrich the brief", lifecycle_tests)
        self.assertNotIn('self.assertIn("not a yes-or-no answer"', lifecycle_tests)

    def test_troubleshooting_splits_only_integration_preflight(self) -> None:
        source = normalized(ROOT / "skills" / "troubleshooting-app" / "SKILL.md")
        self.assertIn("only when both conditions hold", source)
        self.assertIn("failure crosses an integration boundary", source)
        self.assertIn("needed to shape or schedule later dispatches", source)
        self.assertIn("stays in the same worker", source)
        self.assertIn("every other app-level or uncertain failure", source)
        self.assertIn("One agent reproduces the failure", source)

    def test_shared_resource_discovery_stays_with_worker(self) -> None:
        source = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        )
        self.assertIn("worker resolves the target app's actual resource configuration", source)
        self.assertIn("Only a resource shared across concurrent tasks is locked", source)
        self.assertNotIn("Every port a worktree's dev server actually binds to gets locked", source)
        self.assertNotIn("defaults are not safe to leave unexamined", source)

    def test_peek_mechanics_follow_current_artifact_schema(self) -> None:
        source = normalized(
            ROOT / "skills" / "peeking-work" / "references" / "peek-mechanics.md"
        )
        self.assertIn("instruction records mode, session_id, and repo_root", source)
        self.assertIn("launch receipt records the agent name and pane", source)
        self.assertIn(
            "status record supplies progress state, note, optional evidence references",
            source,
        )
        self.assertIn("rather than routing data", source)
        self.assertNotIn("dispatch/<session_id>.json", source)

    def test_coordination_lifecycle_is_event_driven(self) -> None:
        orchestrator = normalized(ROOT / "skills" / "i-am-orchestrator" / "SKILL.md")
        self.assertIn("Keep the lifecycle event-driven", orchestrator)
        self.assertIn("A dispatch reports itself", orchestrator)
        self.assertIn(
            "spend the time between events on other coordination or on the user's conversation",
            orchestrator,
        )
        self.assertIn(
            "when observed evidence and its recorded state actually disagree, or when the user asks",
            orchestrator,
        )
        self.assertNotIn("watch status", orchestrator)
        self.assertNotIn("every dispatch is observed or terminal", orchestrator)

        roles = normalized(ROOT / "docs" / "roles.md")
        self.assertIn("status-event handling", roles)
        self.assertIn(
            "That persisted status and its notification are what drive the coordination lifecycle",
            roles,
        )
        self.assertNotIn("status observation", roles)
        self.assertNotIn("observe status", roles)

        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn(
            "Report, then run the lifecycle on the dispatch's own events", dispatching
        )
        self.assertIn(
            "Between events the task is running and the main agent is free for other coordination",
            dispatching,
        )

        shipping = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("the answer arrives as its next status event", shipping)
        self.assertNotIn("pane/process observation", shipping)

        for reference in ("cross-session-coordination.md", "dispatch-mechanics.md"):
            source = normalized(
                ROOT / "skills" / "dispatching-work" / "references" / reference
            )
            self.assertNotIn("process/watcher observation", source)

    def test_orchestrator_reports_compactly_and_asks_one_decision_at_a_time(
        self,
    ) -> None:
        roles = normalized(ROOT / "docs" / "roles.md")
        orchestrator = normalized(ROOT / "skills" / "i-am-orchestrator" / "SKILL.md")
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        plan_mechanics = normalized(
            ROOT / "skills" / "dispatching-work" / "references" / "plan-mechanics.md"
        )

        for source in (roles, orchestrator):
            self.assertIn("current coordination delta", source)
            self.assertIn("harness-native ask-question interface", source)
            self.assertIn("exactly one decision", source)
            self.assertIn("wait", source)

        self.assertIn("one** batch-wide", boss_say)
        self.assertIn("one plan-confirmation decision", boss_say)
        self.assertLess(
            boss_say.index("one** batch-wide"),
            boss_say.index("one plan-confirmation decision"),
        )
        self.assertIn("For headless Codex", boss_say)
        self.assertIn("headless Claude failed note", boss_say)
        self.assertIn("--retry-failed-plan-task", boss_say)
        self.assertNotIn("every progress report from here on", boss_say)
        self.assertNotIn("repeat the prior finding instead", boss_say)
        self.assertIn("Don't re-peek or report unchanged idleness", boss_say)
        self.assertIn("unchanged idleness stays quiet", boss_say)

        self.assertIn("Present any later decision in a later ask-question interaction", dispatching)
        self.assertIn("For headless Codex", dispatching)
        self.assertIn("headless Claude user decision arrives as terminal failed", dispatching)
        self.assertIn("fresh-slug answer retry", dispatching)
        self.assertNotIn("point the user at the pane for the other checkpoints", dispatching)

        self.assertIn("presents one user-owned decision", plan_mechanics)
        self.assertIn("waits before presenting another", plan_mechanics)
        self.assertIn("Headless Claude reports failed", plan_mechanics)
        self.assertIn("--retry-failed-plan-task", plan_mechanics)
        self.assertIn("fresh slug and the answer in the new brief", plan_mechanics)
        self.assertIn("On an interactive awaiting-user-input notification", plan_mechanics)
        self.assertIn("On a headless Codex notification", plan_mechanics)
        self.assertNotIn(
            "tell the user which task is asking and which worker pane to answer (from herdr_pane_id), then leave it alone. The plan loop",
            plan_mechanics,
        )

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

    def test_orchestrator_handoff_requires_approval_and_moves_ownership(self) -> None:
        roles = normalized(ROOT / "docs" / "roles.md")
        skill = normalized(ROOT / "skills" / "handoff-orchestrator" / "SKILL.md")
        launcher = normalized(ROOT / "scripts" / "run-straw-boss-script.py")

        self.assertIn("first presents one approval decision", roles)
        self.assertIn("Run ADAAV lightly", roles)
        self.assertIn("internal ordering rather than a response template", roles)
        self.assertIn("status events, investigation, scheduling, reporting, and cleanup all belong to the receiver", roles)
        self.assertIn("A new tab is created only after the user approves", skill)
        self.assertIn("Pass only goal and scope", skill)
        self.assertIn("Continue only the scope passed through --retains", skill)
        self.assertIn('"accept-orchestrator-handoff.py"', launcher)
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("Branch: Receiving an orchestrator handoff", boss_say)
        self.assertIn("After the owner, coordination graph, and reality anchor are established", boss_say)
        self.assertIn("--owner <owning-skill>", boss_say)
        self.assertIn("--coordination-graph '<graph>'", boss_say)
        self.assertIn("--reality-anchor '<anchor>'", boss_say)

    def test_shipping_sync_is_conditional_and_scope_is_local(self) -> None:
        source = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("If the primary checkout tracks the merged base", source)
        self.assertNotIn("once the worktree is removed, sync the app's primary checkout too", source)
        self.assertNotIn("This finding needs DB/infra access I don't have", source)

    def test_every_grant_of_the_verification_method_is_scoped_to_the_anchor(
        self,
    ) -> None:
        """The mandatory contract and the skills have to agree on one boundary.

        `1da9e55` broke exactly this: the generated contract went on granting
        the worker an unqualified "verification method" while the new skills
        started fixing the reality anchor at dispatch, so a worker received two
        instructions and no rule for which one wins. Scoping the grant is what
        makes both true at once, so every surface that states the grant has to
        carry the scope -- including the contract the dispatcher really builds.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
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
        self.assertGreaterEqual(
            sum(
                1
                for text in surfaces.values()
                for sentence in sentences(text)
                if "verification method" in sentence.lower()
            ),
            5,
            "the grant vanished instead of being scoped",
        )

    def test_the_anchor_is_the_coordinators_and_the_method_inside_it_is_not(
        self,
    ) -> None:
        """Both halves of the boundary, stated where authority is defined."""
        roles = normalized(ROOT / "docs" / "roles.md")
        self.assertIn("The reality anchor is coordination; the method inside it is work", roles)
        self.assertIn("The main agent names which anchor proves a task", roles)
        self.assertIn("Naming the anchor is not naming the tests", roles)

        graph = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("Naming the anchor is not naming the tests", graph)
        # The testing anchor's own escalation stays with the worker on every
        # surface that spells the default out.
        for name, source in (("choosing-graph", graph), ("docs/roles.md", roles)):
            self.assertIn("smallest credible seam that can go red before the change", source, name)
            self.assertIn("integration or E2E", source, name)
        self.assertIn(
            "the worker escalates to integration or E2E when the target project's own conventions call for it",
            graph,
        )

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

    def test_only_orchestrator_worker_is_described_as_writing_a_dispatch_plan(
        self,
    ) -> None:
        graph_source = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn(
            "the only graph that writes ~/.straw-boss/plans/<slug>/plan.json",
            graph_source,
        )
        self.assertIn("the other two carry no dispatch plan", graph_source)
        # boss-say is the one skill that writes a plan for work it did not
        # decompose, so it has to name the same graph.
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("A capped batch is always orchestrator-worker", boss_say)

    def test_a_dispatch_time_claim_is_released_from_every_terminal_path(self) -> None:
        """F: the batch/plan path ends in auto-detach, not the Wrap-up branch.

        Both have to reach the release rule, and the rule itself has to say it
        applies to every terminal status -- `done` included.
        """
        shared = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        )
        self.assertIn(
            "Releasing every lock on a wrapped-up instruction -- every terminal "
            "status, every path",
            shared.replace("—", "--"),
        )
        self.assertIn("done is not an exception", shared)
        for name, source in (
            ("Wrap-up branch", normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")),
            (
                "plan auto-detach",
                normalized(
                    ROOT
                    / "skills"
                    / "dispatching-work"
                    / "references"
                    / "plan-mechanics.md"
                ),
            ),
        ):
            self.assertIn(
                "Releasing every lock on a wrapped-up instruction", source, name
            )

    def test_the_claim_port_command_is_written_out_exactly_once(self) -> None:
        """Single source of truth, checked by counting the real command."""
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

    def test_read_only_dispatch_skills_name_the_anchor_their_evidence_feeds(
        self,
    ) -> None:
        for skill in ("inspecting-app", "investigating-app"):
            source = normalized(ROOT / "skills" / skill / "SKILL.md")
            self.assertIn("what this work's anchor attacks", source, skill)
            self.assertIn("adversarial-review is the reality anchor", source, skill)

    def test_the_anchor_set_is_closed_and_identical_on_every_surface(self) -> None:
        """A main agent has to name an anchor from a list, so the list has to be
        the same list everywhere.

        Naming a fifth kind in the skill while `docs/roles.md` enumerates four
        leaves audit and research dispatches with no nameable category -- the
        same shape of defect as an unscoped verification-method grant.
        """
        graph_body = (ROOT / "skills" / "choosing-graph" / "SKILL.md").read_text()
        anchors_section = graph_body.partition("## Reality anchors")[2].partition("\n## ")[0]
        named = re.findall(r"^- \*\*([a-z-]+)\*\*", anchors_section, re.MULTILINE)
        self.assertEqual(
            named, ["testing", "pseudo-human", "human", "adversarial-review"]
        )

        roles = normalized(ROOT / "docs" / "roles.md")
        enumeration = [
            sentence
            for sentence in sentences(roles)
            if "names which anchor proves a task" in sentence
        ]
        self.assertEqual(
            len(enumeration), 1, "docs/roles.md enumerates the anchors exactly once"
        )
        for anchor in ("testing", "pseudo-human", "human", "adversarial review"):
            self.assertIn(anchor, enumeration[0], anchor)
        # Anything the skill anchors on has to be one of those four.
        self.assertIn("adversarial-review is its anchor", " ".join(graph_body.split()))

    def test_no_surface_gives_the_worker_the_anchor_category(self) -> None:
        """The mirror of the scoping test.

        Scoping the grant is only half the boundary: a surface that has the
        worker picking the anchor itself would still satisfy the scope check,
        because the word "anchor" would be right there in the sentence.
        """
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

    def test_the_lifecycle_mode_question_is_the_users_reading_of_the_work(self) -> None:
        """The mode is the user's reading, and both skills that raise it agree
        it can be answered before the work's scope is known."""
        shipping = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("how the user regards this piece of work", shipping)
        self.assertIn("the user is answering with the consequence in view", shipping)
        troubleshooting = normalized(
            ROOT / "skills" / "troubleshooting-app" / "SKILL.md"
        )
        self.assertIn("which they can answer before the cause is known", troubleshooting)
        self.assertIn("It owns the mode decision", troubleshooting)

    def test_the_deleted_allowed_list_exception_is_actually_gone(self) -> None:
        """A record of a deletion has to be true of the tree it describes.

        `969e0bd`'s commit message, this change's `design.md`, and its
        `verification.md` all state that `dispatching-work` Task 3's "or the
        reality anchor" allowed-list exception was deleted rather than
        reworded. The diff only appended a second clause after it, so three
        records -- two of them the change's own acceptance evidence -- disagree
        with the file they describe.
        """
        spec = ROOT / "docs" / "specs" / "2026-08-28-anchor-authority-boundary"
        self.assertIn("That clause is gone", normalized(spec / "design.md"))
        self.assertIn(
            "allowed-list exception is deleted, not rewritten",
            normalized(spec / "verification.md"),
        )

        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        allowed = [
            sentence
            for sentence in sentences(dispatching)
            if "brief statement" in sentence and "traces to" in sentence
        ]
        self.assertEqual(len(allowed), 1, "one allowed-source list, in Task 3")
        self.assertNotIn("reality anchor", allowed[0])
        # The anchor is still required in the brief -- as a named element, not
        # as an exception to the source rule.
        self.assertIn("the brief names the anchor it settled on", dispatching)

    def test_the_contract_says_what_to_do_when_a_dispatch_names_no_anchor(self) -> None:
        """The generated contract asserts that the dispatch named an anchor.

        Nothing carries the anchor structurally -- it lives in the free-text
        brief -- so that assertion can be false on arrival, and a worker reading
        it literally cannot tell how far its own verification authority runs.
        The contract degrades to the checkpoint that owns the gap rather than
        widening the grant to cover the anchor category itself.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
        finally:
            sys.path.pop(0)

        contract = " ".join(
            dispatch_state.render_dispatch_contract(
                instruction_path=Path("/home/boss/.straw-boss/dispatch/app--slug.json"),
            )
            .replace("`", "")
            .split()
        )
        self.assertIn("the reality anchor this dispatch names", contract)
        self.assertIn(
            "ask the main agent to name the anchor when this dispatch does not",
            contract,
        )

    def test_the_release_rule_covers_both_locks_its_pointer_claims(self) -> None:
        """`dispatching-work`'s Wrap-up step 3 sends the reader to a paragraph
        that denies one of the two cases the step says it covers.

        The paragraph opens "The worker never claimed this lock ... it has
        nothing to report about it", which is true of the dispatch-time claim
        and false of a lock the worker claimed inside its own task and reported
        without confirming release -- the second case the pointer names.
        """
        shared = (
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        )
        release = [
            block
            for block in paragraphs(shared.read_text())
            if "Releasing every lock on a wrapped-up instruction" in block
        ]
        self.assertEqual(len(release), 1, "the release rule lives in one paragraph")
        for case in (
            "The worker never claimed the dispatch-time lock",
            "a lock the worker claimed inside its own task and reported "
            "without confirming release is released here too",
        ):
            self.assertIn(case, release[0], case)

        # A new wrap-up step needs an acceptance condition of its own.
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn(
            "every shared-resource lock on this instruction is released before "
            "wrap-up-task.py runs",
            dispatching,
        )

    def test_no_retired_coordination_alias_is_live_in_the_skills(self) -> None:
        """`_Avoid_` is per-concept aliasing, not a word ban.

        "subagent", "model", and "role" are each retired as the name of one
        concept and live as the name of another, so a blanket scan would be
        wrong. The three coordination entries `969e0bd` added retire names for
        the coordination concepts themselves, none of which carries a second
        live sense, and those have to be dead in the skills -- otherwise the
        glossary retires a name the plugin is still using, in a different sense,
        in the same task that states the concept.
        """
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

    def test_troubleshooting_names_the_anchor_on_both_of_its_branches(self) -> None:
        """`choosing-graph` names three skills whose evidence references its
        read-only anchor attacks; only two of them said so.

        `troubleshooting-app` also is not read-only as a whole -- its default
        branch lands a fix -- so the rule reaches its integration preflight, not
        the skill.
        """
        troubleshooting = normalized(ROOT / "skills" / "troubleshooting-app" / "SKILL.md")
        self.assertIn(
            "an independent agent's adversarial review of the account",
            troubleshooting,
        )
        self.assertIn("the fix is anchored on testing", troubleshooting.lower())

        graph = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("adversarial-review is its anchor", graph)
        self.assertIn("A troubleshooting branch that lands a fix uses testing", graph)

    def test_one_graph_wins_when_single_loop_and_fan_out_both_fit(self) -> None:
        """The criterion calls itself observable, so overlapping bullets need a
        decision, not a reader's taste.

        A coordinator driving one dispatch while running its own subagents, and
        a worker that brought a coworker and also runs subagents, each satisfy
        `single-loop` and `sub-agent fan-out/fan-in` as written.
        """
        source = (ROOT / "skills" / "choosing-graph" / "SKILL.md").read_text()
        tie_break = "whether a branch of the work itself runs in a subagent"
        deciding = [block for block in paragraphs(source) if tie_break in block]
        self.assertEqual(len(deciding), 1, "one tie-break, stated once")
        # It adjudicates those two and stops there. `orchestrator-worker` is
        # the boundary with a mechanical consequence -- it alone writes a
        # plan.json -- so a batch that also runs an item in a subagent stays
        # that shape.
        self.assertIn("single-loop", deciding[0])
        self.assertIn("sub-agent fan-out/fan-in", deciding[0])
        self.assertNotIn("orchestrator-worker", deciding[0])
        # The exemption and the tie-break are one rule: the anchor's own check
        # is the case the tie-break must not sweep into fan-out.
        self.assertIn("never changes the graph", deciding[0])

    def test_every_dispatch_path_reaches_choosing_graph(self) -> None:
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("choosing-graph", boss_say)
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn(
            "Invoke choosing-graph when the graph and anchor are not fixed yet",
            dispatching,
        )
        self.assertIn("The brief then names the reality anchor it settled on", dispatching)

    def test_lifecycle_mode_names_are_consistent_across_every_live_surface(self) -> None:
        stale = re.compile(r"full[ -]flow|light[ -]flow", re.IGNORECASE)
        offenders = [
            f"{path.relative_to(ROOT).as_posix()}:{number}"
            for path in prose_surfaces(include_scripts=True)
            for number, line in instruction_lines(path)
            if stale.search(line)
        ]
        self.assertEqual(offenders, [])


    def test_the_adversarial_review_obligation_reaches_every_worker(self) -> None:
        """`choosing-graph` makes adversarial review unconditional for every
        ordinary programming change and assigns the action to the worker.

        The obligation never varies, so a per-dispatch free-text brief is the
        wrong carrier: `shipping-task` -- the only path an ordinary programming
        change takes -- never mentioned it, the generated contract never
        mentioned it, and the brief carries the anchor beside which it runs,
        not the review itself. The only delivery left was the worker choosing
        to read a skill nothing told it to read.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
        finally:
            sys.path.pop(0)

        bullets = contract_bullets(
            dispatch_state.render_dispatch_contract(
                instruction_path=Path("/home/boss/.straw-boss/dispatch/app--slug.json"),
            )
        )
        carrying = [
            bullet
            for bullet in bullets
            if "adversarial review" in bullet
        ]
        self.assertEqual(
            len(carrying), 1, "the obligation is one standing contract bullet"
        )
        self.assertIn("one coherent change-set", carrying[0])
        self.assertIn("one fresh-context adversarial review", carrying[0])
        self.assertIn("The brief states when the main agent owns this review", carrying[0])
        # A standing rule cannot be scoped to one transport.
        self.assertNotIn("herdr-pane", carrying[0])
        self.assertNotIn("claude-p", carrying[0])

    def test_both_routes_that_discharge_the_review_are_named(self) -> None:
        """The rule assigned the action to the worker alone, while this repo's
        own practice dispatches the review from the coordinator after the
        change lands. A rule its own project does not follow is the defect
        class this spec family exists to close, so both routes are named.
        """
        graph = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("The lifecycle owner records the review once", graph)
        self.assertIn("one coherent change-set", graph)

    def test_the_skill_that_carries_ordinary_changes_states_and_checks_the_review(
        self,
    ) -> None:
        """H's original complaint, for the skill three rounds never named.

        `shipping-task` carries every ordinary programming change and said
        nothing about the review those changes are required to carry, and no
        step anywhere confirmed one had happened.
        """
        shipping = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("the single review disposition required by choosing-graph", shipping)
        self.assertIn("one review disposition", shipping)

    def test_the_missing_anchor_fallback_applies_in_every_dispatch_mode(self) -> None:
        """Every provider gets an executable anchor fallback for its lifecycle."""
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
        finally:
            sys.path.pop(0)

        path = Path("/home/boss/.straw-boss/dispatch/app--slug.json")
        interactive = dispatch_state.render_dispatch_contract(path)
        headless_codex = dispatch_state.render_dispatch_contract(
            path, mode="claude-p", agent_kind="codex"
        )
        headless_claude = dispatch_state.render_dispatch_contract(
            path, mode="claude-p", agent_kind="claude"
        )

        for contract in (interactive, headless_codex):
            self.assertIn("name the anchor when this dispatch does not", contract)
            self.assertIn("awaiting-main-agent", contract)
        self.assertIn("does not name the anchor", headless_claude)
        self.assertIn("report terminal `failed`", headless_claude)
        fallback = headless_claude.split("does not name the anchor", 1)[1].split("\n-", 1)[0]
        self.assertNotIn("awaiting-main-agent", fallback)

    def test_the_brief_source_rule_governs_what_the_brief_says_about_the_work(
        self,
    ) -> None:
        """Task 3's Verification opens with a universal over *every* brief
        statement and then, in the next clause, requires a statement none of
        the three listed sources can produce.

        The anchor is a decision the dispatch makes, not a fact the main agent
        already held, so the universal has to say what it actually governs
        rather than gain a fourth source -- which would restore the deleted
        exception under a new name.
        """
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn(
            "every brief statement about the work traces to the user request, "
            "a necessary hint or constraint, or an already-known coordination state",
            dispatching,
        )
        self.assertIn(
            "the coordination this dispatch fixed is the brief's own", dispatching
        )
        # The brief carries the review route too, since the contract's default
        # is only overridden by what the brief says.
        self.assertIn(
            "the brief names the anchor it settled on without prescribing the "
            "method inside it",
            dispatching,
        )
        self.assertIn(
            "says so when the main agent runs the adversarial review instead of "
            "the worker",
            dispatching,
        )

    def test_the_coordination_graph_is_named_where_authority_is_defined(self) -> None:
        """`docs/roles.md` calls itself the single execution-time definition of
        who decides what, and `choosing-graph` calls the graph and the anchor
        both coordination -- but only the anchor was defined there, and the
        stance the SessionStart hook injects listed only the anchor too.
        """
        roles = normalized(ROOT / "docs" / "roles.md")
        self.assertIn(
            "The coordination graph is coordination too", roles
        )
        self.assertIn("a dispatched agent states its own for its own task", roles)
        orchestrator = normalized(ROOT / "skills" / "i-am-orchestrator" / "SKILL.md")
        self.assertIn("the coordination graph", orchestrator)

    def test_orchestrator_worker_is_settled_before_the_two_way_tie_break(self) -> None:
        """The tie-break adjudicates `single-loop` against fan-out and stops
        there, on purpose. That leaves the third overlap unstated: a
        coordinator running more than one app-rooted worker while also running
        its own subagents satisfies `orchestrator-worker` and fan-out at once,
        and only one of them writes a plan.
        """
        source = (ROOT / "skills" / "choosing-graph" / "SKILL.md").read_text()
        precedence = [
            block
            for block in paragraphs(source)
            if "settled ahead of the other two" in block
        ]
        self.assertEqual(len(precedence), 1, "one precedence rule, stated once")
        self.assertIn("orchestrator-worker", precedence[0])
        self.assertIn("whatever else runs beside it", precedence[0])
        # It is a separate rule from the pair tie-break, which stays scoped.
        self.assertNotIn(
            "whether a branch of the work itself runs in a subagent", precedence[0]
        )

    def test_the_release_rules_own_title_covers_both_locks_it_releases(self) -> None:
        """`cc690f3` widened the paragraph to a second lock that is not a
        dispatch-time claim and left the title reading "Releasing a
        dispatch-time claim" -- which is also how both pointers locate it.
        """
        shared = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        ).replace("—", "--")
        self.assertIn(
            "Releasing every lock on a wrapped-up instruction -- every terminal "
            "status, every path",
            shared,
        )
        self.assertNotIn("Releasing a dispatch-time claim", shared)
        for name, source in (
            ("Wrap-up branch", normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")),
            (
                "plan auto-detach",
                normalized(
                    ROOT
                    / "skills"
                    / "dispatching-work"
                    / "references"
                    / "plan-mechanics.md"
                ),
            ),
        ):
            self.assertIn("Releasing every lock on a wrapped-up instruction", source, name)
            self.assertNotIn("Releasing a dispatch-time claim", source, name)

    def test_a_superseded_spec_bullet_carries_its_forward_marker(self) -> None:
        """A later spec declares one earlier bullet superseded; the bullet
        itself carried no marker, so a reader arriving at the earlier spec
        reads a description the tree no longer matches.

        The repo's own convention is a forward marker on the superseded record
        -- inline for one bullet, per `docs/qa/discover-qa-2026-08-26-launcher.md`.
        """
        superseding = "2026-08-28-close-rereview-findings"
        declaration = re.search(
            r"This supersedes the ([0-9a-z-]+) bullet",
            normalized(ROOT / "docs" / "specs" / superseding / "spec.md"),
        )
        self.assertIsNotNone(declaration, "the superseding claim is still stated")
        superseded = ROOT / "docs" / "specs" / declaration.group(1) / "spec.md"
        marked = [
            line
            for line in normalized(superseded).split(". ")
            if "Superseded on" in line
        ]
        self.assertNotEqual(marked, [], f"{superseded.name} carries no forward marker")
        self.assertIn(superseding, " ".join(marked))

    def test_every_path_that_lands_a_change_checks_the_review(self) -> None:
        """`shipping-task` is not the only path an ordinary programming change
        takes: `boss-say`'s capped batch dispatches its items through
        `dispatching-work` Tasks 1-5 directly and closes them out in its own
        Task 7, never reaching `shipping-task` Task 6 -- and a direct
        `dispatching-work` close-out (`boss-say`'s own "close out `<task>`"
        passthrough) reaches neither.

        A rule that names two acceptance points while three paths land changes
        is the same defect class it exists to close.
        """
        for path in (
            ROOT / "skills" / "shipping-task" / "SKILL.md",
            ROOT / "skills" / "boss-say" / "SKILL.md",
            ROOT / "skills" / "dispatching-work" / "SKILL.md",
        ):
            source = normalized(path)
            self.assertIn("completion reference", source, path.name)
            self.assertIn("review disposition", source, path.name)

    def test_a_directly_closed_out_dispatch_dispositions_its_own_review(self) -> None:
        """The third acceptance point `choosing-graph` now names:
        `boss-say`'s own "close out `<task>`" passthrough (Branch: Status
        query, or closing out one dispatch) lands control on
        `dispatching-work`'s Wrap-up branch directly, past both
        `shipping-task` Task 6 and `boss-say` Task 7 -- so that branch has to
        carry the disposition itself, for whatever reaches it without either.
        """
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn("choosing-graph's single review checkpoint", dispatching)
        self.assertIn("one review disposition before archive", dispatching)

    def test_plan_auto_detach_dispositions_the_review_before_archiving(self) -> None:
        """A fourth real close-out path exists beside the three
        `choosing-graph` names: `plan-mechanics.md`'s "Auto-detach on
        terminal state" is a complete, self-contained mechanical procedure
        -- invoked by `dispatching-work`'s own wave loop on every
        `done`/`failed` event -- that goes straight from closing the pane to
        `wrap-up-task.py`, which archives the instruction, with no
        disposition gate of its own. Unlike `boss-say`'s batch flow (which
        has a guaranteed later Task 7 pass), nothing else guarantees the
        review gets confirmed for a `work-on`-produced plan task if this
        procedure's own terminal-event reaction gets there first. The
        auto-detach procedure must carry the same guard the other three
        acceptance points do, so it is safe to follow on its own.
        """
        plan_mechanics = normalized(
            ROOT / "skills" / "dispatching-work" / "references" / "plan-mechanics.md"
        )
        self.assertIn("choosing-graph's single review checkpoint", plan_mechanics)
        wrap_up_index = plan_mechanics.index("Call wrap-up-task.py --app")
        disposition_index = plan_mechanics.index(
            "For a landed programming change"
        )
        self.assertLess(
            disposition_index,
            wrap_up_index,
            "the review must be dispositioned before wrap-up-task.py archives "
            "the instruction, or the gate reads too late to matter",
        )

    def test_choosing_graph_names_the_plan_auto_detach_path_too(self) -> None:
        """`choosing-graph`'s enumeration named exactly three acceptance
        points (`shipping-task` Task 6, `boss-say` Task 7,
        `dispatching-work`'s own Wrap-up branch) even after
        `plan-mechanics.md`'s auto-detach gained its own guard -- a fourth
        real textual location that now discharges the same obligation. An
        authoritative list that omits a real discharge point is the same
        defect class this whole file exists to catch.
        """
        graph = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("The lifecycle owner records the review once", graph)

    def test_shipping_task_dispositions_a_work_on_plans_review_per_task(self) -> None:
        """Task 6 was written entirely in one-agent lifecycle language
        ("Once the agent reports the lifecycle is complete") while
        `work-on:29` says `shipping-task` runs a multi-app/phase request as
        separate per-app cycles -- leaving unstated whether disposition runs
        once per plan task or once for the whole plan.
        """
        shipping = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn(
            "For a work-on-produced plan (Task 1), this task runs once per "
            "plan task, as each one's own lifecycle completes — not once "
            "for the whole plan",
            shipping,
        )
        self.assertIn("each plan task closes once", shipping)

    def test_boss_say_confirms_the_items_own_reference_before_dispositioning_it(
        self,
    ) -> None:
        """`shipping-task` Task 6 confirms the merge or commit reference
        before dispositioning the review against it. `boss-say` Task 7
        dispositioned against a reference it never confirmed -- Task 5 only
        counts, refills, and relays, and Task 7's own data source is the
        status file's free-text `note`.
        """
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("confirm its completion reference", boss_say)

    def test_shipping_task_dispositions_the_review_before_invoking_wrap_up(
        self,
    ) -> None:
        """An independent adversarial review of this spec family's own
        commit found the exact gap `dispatching-work`'s new Wrap-up-branch
        guard exists to prevent: Task 6's confirm-and-disposition paragraph
        sat two paragraphs after "Then invoke `dispatching-work`'s wrap-up
        branch", so a literal reading invokes the branch first -- at which
        point the branch's own guard ("neither shipping-task Task 6 ...
        already dispositioned") is still true, runs its own disposition, and
        Task 6's later paragraph then runs it again.
        """
        source = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        invoke_index = source.index("invoke dispatching-work's wrap-up branch")
        disposition_index = source.index("record the single review disposition")
        self.assertLess(
            disposition_index,
            invoke_index,
            "the review must be dispositioned before the wrap-up branch is "
            "invoked, or the branch's own guard still reads undispositioned",
        )

    def test_boss_say_dispositions_the_review_only_when_no_earlier_pass_did(
        self,
    ) -> None:
        """The reciprocal half of `dispatching-work`'s guard: that branch
        already skips disposition when `shipping-task` Task 6 or `boss-say`
        Task 7 got there first, but nothing stopped a batch item manually
        closed out mid-batch through the "close out `<task>`" passthrough
        (dispositioned once at the Wrap-up branch) from being dispositioned
        again once the whole batch later reaches Task 7. `plan-mechanics.md`'s
        auto-detach Step 2 -- run by every batch item's own per-item
        auto-detach (Task 5 step 4) before Task 7 ever runs -- is the same
        kind of earlier pass and needs the identical exemption, or Task 7
        redundantly re-attempts a disposition every batch item already got.
        """
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("one review disposition", boss_say)

    def test_the_workers_own_coordination_graph_obligation_reaches_the_contract(
        self,
    ) -> None:
        """`docs/roles.md` says a dispatched agent states its own
        coordination graph for its own task, but nothing a worker is
        required to read ever carried it -- every live "go invoke
        `choosing-graph`" pointer for this purpose sat on the coordinator's
        own task text (`dispatching-work` Task 3, `boss-say` Task 1), never
        the contract or the brief.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
        finally:
            sys.path.pop(0)

        contract = dispatch_state.render_dispatch_contract(
            instruction_path=Path("/home/boss/.straw-boss/dispatch/app--slug.json"),
        )
        normalized_contract = " ".join(contract.replace("`", "").split())
        self.assertIn(
            "State your own coordination graph for this task before you "
            "start, through choosing-graph",
            normalized_contract,
        )

    def test_the_coordination_graph_glossary_entry_states_the_workers_half_too(
        self,
    ) -> None:
        """The adjacent `Reality anchor` glossary entry states both halves --
        who names it, who works inside it -- and `Coordination graph` stated
        only the coordinator's half.
        """
        context = normalized(ROOT / "CONTEXT.md")
        self.assertIn(
            "The coordinator states it before it dispatches; a dispatched "
            "agent states its own for its own task",
            context,
        )

    def test_the_review_route_offers_bringing_coworker_only_where_it_can_run(
        self,
    ) -> None:
        """A writable coworker's own bullet already forbids it from
        coordinating another coworker (nesting stops at one level,
        `docs/roles.md`), and `bringing-coworker` itself only runs from an
        interactive worker sharing its own live Herdr tab -- a headless
        `claude-p` worker has none. The obligation bullet named "a coworker"
        as a route for every reader regardless.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dispatch_state
        finally:
            sys.path.pop(0)

        def review_bullet(coworker_context):
            bullets = contract_bullets(
                dispatch_state.render_dispatch_contract(
                    instruction_path=Path(
                        "/home/boss/.straw-boss/dispatch/app--slug.json"
                    ),
                    coworker_context=coworker_context,
                )
            )
            carrying = [b for b in bullets if "adversarial review" in b]
            self.assertEqual(len(carrying), 1)
            return carrying[0]

        top_level = review_bullet(None)
        self.assertIn("bringing-coworker", top_level)

        for coworker_context in (
            {"coworker_writable_paths": ["src/"]},
            {"coworker_writable_paths": []},
        ):
            nested = review_bullet(coworker_context)
            self.assertNotIn("coworker", nested)

    def test_the_superseded_marker_is_its_own_block(self) -> None:
        """A marker appended to the end of the claim it retires reads as part
        of that claim. It has to be separable from the sentence it marks."""
        superseded = (
            ROOT
            / "docs"
            / "specs"
            / "2026-08-28-anchor-authority-boundary"
            / "spec.md"
        )
        blocks = [
            block
            for block in paragraphs(superseded.read_text())
            if block.startswith("Superseded on")
        ]
        self.assertEqual(len(blocks), 1, "the marker stands on its own")
        self.assertIn("2026-08-28-close-rereview-findings", blocks[0])

    def test_the_dispatch_files_are_the_lifecycle_record_not_a_plan_on_both_surfaces(
        self,
    ) -> None:
        """A main agent reads `boss-say`; a dispatched worker reads
        `choosing-graph` and never reads `boss-say`. The rule that
        `single-loop`/`sub-agent fan-out/fan-in` write no plan or repo spec
        document, and the rule that the dispatch instruction/contract/status
        files are ephemeral lifecycle mechanics rather than that plan or spec,
        both need a reader on each side or one surface can drift from the
        other. Requiring "archived" alongside the no-plan claim in the same
        paragraph also guards the fix from overshooting into claiming an
        app-rooted dispatch writes no files at all.
        """
        for name in ("boss-say", "choosing-graph"):
            source = (ROOT / "skills" / name / "SKILL.md").read_text()
            block = [p for p in paragraphs(source) if "the dispatch's lifecycle record" in p]
            self.assertEqual(len(block), 1, name)
            self.assertIn("archived once the dispatch wraps up", block[0], name)
            self.assertIn(
                "no repo-internal Straw Boss planning or spec document",
                block[0],
                name,
            )
            self.assertIn("plan.json", block[0], name)
            # The mode question stays the user's reading of the work, not a
            # scale judgment -- this rule must never reach for either term.
            self.assertNotIn("solo-mode", block[0], name)
            self.assertNotIn("team-mode", block[0], name)

    def test_boss_say_names_its_own_graph_vocabulary_for_a_single_item(self) -> None:
        """boss-say has to carry the durability rule in its own words -- a
        main agent reading only this file, never `choosing-graph`, still has
        to land on the same two graph names for its own single item."""
        boss_say = (ROOT / "skills" / "boss-say" / "SKILL.md").read_text()
        block = [
            p
            for p in paragraphs(boss_say)
            if "no repo-internal Straw Boss planning or spec document" in p
        ]
        self.assertEqual(len(block), 1)
        self.assertIn("single-loop", block[0])
        self.assertIn("sub-agent fan-out/fan-in", block[0])

    def test_single_loop_and_review_have_bounded_process_cost(self) -> None:
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        graph = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")

        self.assertIn("current agent carries a bounded single-loop", boss_say)
        self.assertIn("smallest sufficient execution tier", boss_say)
        self.assertIn("one coherent change-set", graph)
        self.assertIn("one adversarial review", graph)
        self.assertIn("examines the finished change-set directly", graph)
        self.assertIn("nits close with an explicit disposition", graph)


if __name__ == "__main__":
    unittest.main()
