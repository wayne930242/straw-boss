from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class AgentNamingTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))

    def tearDown(self) -> None:
        sys.path.pop(0)

    def test_derives_role_and_app_into_a_readable_handle(self) -> None:
        import agent_naming

        self.assertEqual(agent_naming.derive_agent_name("worker", "api"), "api-worker")
        self.assertEqual(agent_naming.derive_agent_name("coworker", "web"), "web-coworker")
        self.assertEqual(
            agent_naming.derive_agent_name("coordinator", "straw-boss"),
            "straw-boss-coordinator",
        )

    def test_derived_name_always_matches_the_format_pattern(self) -> None:
        import agent_naming

        for role in ("worker", "coworker", "coordinator"):
            for app in ("api", "web", "database", "straw-boss"):
                name = agent_naming.derive_agent_name(role, app)
                self.assertRegex(name, agent_naming.NAME_PATTERN.pattern)
                self.assertLessEqual(len(name), agent_naming.MAX_NAME_LENGTH)

    def test_sanitizes_an_app_name_that_is_not_already_kebab_case(self) -> None:
        import agent_naming

        self.assertEqual(
            agent_naming.derive_agent_name("worker", "REST API v3"), "rest-api-v3-worker"
        )

    def test_truncates_a_long_app_name_from_the_tail_to_fit_the_cap(self) -> None:
        import agent_naming

        name = agent_naming.derive_agent_name(
            "worker", "moldplan-frontend-2-production-schedule-ui"
        )
        self.assertLessEqual(len(name), agent_naming.MAX_NAME_LENGTH)
        self.assertTrue(name.startswith("moldplan-frontend"))
        self.assertTrue(name.endswith("-worker"))

    def test_rejects_a_role_that_leaves_no_room_for_any_app_signal(self) -> None:
        import agent_naming

        with self.assertRaises(ValueError):
            agent_naming.derive_agent_name("x" * 32, "api")

    def test_unique_name_passes_through_when_not_taken(self) -> None:
        import agent_naming

        self.assertEqual(agent_naming.unique_agent_name("api-worker", set()), "api-worker")

    def test_unique_name_appends_a_numeric_suffix_on_collision(self) -> None:
        import agent_naming

        self.assertEqual(
            agent_naming.unique_agent_name("api-worker", {"api-worker"}), "api-worker-2"
        )
        self.assertEqual(
            agent_naming.unique_agent_name("api-worker", {"api-worker", "api-worker-2"}),
            "api-worker-3",
        )

    def test_unique_name_suffix_still_fits_the_cap_for_a_maximal_candidate(self) -> None:
        import agent_naming

        candidate = "a" * agent_naming.MAX_NAME_LENGTH
        result = agent_naming.unique_agent_name(candidate, {candidate})
        self.assertLessEqual(len(result), agent_naming.MAX_NAME_LENGTH)
        self.assertTrue(agent_naming.NAME_PATTERN.match(result))

    def test_live_names_reads_the_agent_list_shape(self) -> None:
        import agent_naming

        payload = {
            "result": {"agents": [{"name": "a"}, {"pane_id": "no-name"}, {"name": "b"}]}
        }
        self.assertEqual(agent_naming.live_names(payload), {"a", "b"})

    def test_live_names_rejects_an_unexpected_shape(self) -> None:
        import agent_naming

        with self.assertRaises(ValueError):
            agent_naming.live_names({"result": {}})

    def test_check_agent_name_cli_accepts_a_valid_unused_name(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "check-agent-name.py"), "--name", "api-worker"],
            input=json.dumps({"result": {"agents": [{"name": "other"}]}}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["name"], "api-worker")

    def test_check_agent_name_cli_rejects_a_name_already_live(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "check-agent-name.py"), "--name", "api-worker"],
            input=json.dumps({"result": {"agents": [{"name": "api-worker"}]}}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already in use", result.stderr)


if __name__ == "__main__":
    unittest.main()
