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
        lifecycle_tests = (
            ROOT / "tests" / "test_dispatched_agent_lifecycle_transport.py"
        ).read_text()
        self.assertNotIn("Do not investigate the target app to enrich the brief", lifecycle_tests)
        self.assertNotIn('self.assertIn("not a yes-or-no answer"', lifecycle_tests)

    def test_troubleshooting_splits_only_integration_preflight(self) -> None:
        source = normalized(ROOT / "skills" / "troubleshooting-app" / "SKILL.md")
        self.assertIn("only when both conditions hold", source)
        self.assertIn("failure crosses an integration boundary", source)
        self.assertIn("needed to shape or schedule later dispatches", source)
        self.assertIn("stays in the same worker", source)
        self.assertIn("every other app-level or uncertain failure", source)
        self.assertIn("One worker reproduces the failure", source)

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

        # Positive, direct phrasing outside the one negation the section title
        # carries by name.
        body = stance.replace("Own the loop, not the work", "")
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
            "Releasing a dispatch-time claim -- every terminal status, every path",
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
            self.assertIn("Releasing a dispatch-time claim", source, name)

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
            self.assertIn(
                "anchors it on an independent agent's adversarial review", source, skill
            )

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


if __name__ == "__main__":
    unittest.main()
