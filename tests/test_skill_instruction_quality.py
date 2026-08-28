from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalized(path: Path) -> str:
    return " ".join(path.read_text().replace("`", "").split())


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
            "specification, design, implementation, and verification method",
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

    def test_dispatch_plan_belongs_to_the_orchestrator_worker_graph_alone(self) -> None:
        source = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("single-loop", source)
        self.assertIn("sub-agent fan-out/fan-in", source)
        self.assertIn("orchestrator-worker", source)
        self.assertIn("the coordinator's shape alone", source)
        self.assertIn(
            "the graph that writes ~/.straw-boss/plans/<slug>/plan.json", source
        )
        self.assertIn("The other two carry no dispatch plan", source)
        self.assertNotIn("supervisor-worker", source)

    def test_choosing_graph_names_four_reality_anchors(self) -> None:
        source = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("**testing** — the default", source)
        self.assertIn("escalates to integration or E2E", source)
        self.assertIn("screenshot and measurement", source)
        self.assertIn(
            "ask the user whether their own risk judgment prefers pseudo-human",
            source,
        )
        self.assertIn(
            "Every ordinary programming change carries adversarial-review", source
        )
        self.assertIn("A human reading code or a document is review", source)

    def test_frontend_anchor_port_is_claimed_at_dispatch(self) -> None:
        source = normalized(ROOT / "skills" / "choosing-graph" / "SKILL.md")
        self.assertIn("claims the port as part of the dispatch", source)
        self.assertIn("binds that number without claiming again", source)

    def test_lifecycle_mode_is_the_users_reading_of_the_work(self) -> None:
        source = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("team-mode", source)
        self.assertIn("solo-mode", source)
        self.assertIn("how the user regards this piece of work", source)
        self.assertNotIn("real size or risk", source)
        self.assertNotIn("diff size", source)
        self.assertNotIn("low-risk changes", source)

    def test_dispatch_carries_the_graph_and_anchor_choice(self) -> None:
        boss_say = normalized(ROOT / "skills" / "boss-say" / "SKILL.md")
        self.assertIn("choosing-graph", boss_say)
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn("names the reality anchor", dispatching)

    def test_shared_resource_reference_covers_the_dispatch_time_port(self) -> None:
        source = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        )
        self.assertIn("A frontend check anchored on human or pseudo-human", source)
        self.assertIn("the main agent runs claim-port once at dispatch", source)
        self.assertIn("worker resolves the target app's actual resource configuration", source)

    def test_lifecycle_mode_names_are_consistent_across_every_live_surface(self) -> None:
        stale = re.compile(r"full[ -]flow|light[ -]flow", re.IGNORECASE)
        surfaces = [
            *(ROOT / "skills").glob("**/*.md"),
            ROOT / "docs" / "architecture.md",
            ROOT / "docs" / "roles.md",
            ROOT / "README.md",
            ROOT / "README.zh-TW.md",
        ]
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted(surfaces)
            if stale.search(path.read_text())
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
