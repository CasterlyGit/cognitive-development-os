from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from cognitive_os.web_mvp import build_server


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "mvp_project_decision_loop.json"


class RunningApp:
    def __init__(self, store_path):
        self.server, self.app = build_server(FIXTURE, store_path, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, value=None, token=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {}
        body = None
        if value is not None:
            body = json.dumps(value)
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-Decision-Token"] = token
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        content_type = response.getheader("Content-Type")
        connection.close()
        if content_type.startswith("application/json"):
            return response.status, json.loads(payload)
        return response.status, payload.decode("utf-8")


class VisualProjectDecisionLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def test_approval_is_real_backend_transition_and_survives_restart(self):
        store = Path(self.temp.name) / "approve.jsonl"
        first = RunningApp(store)
        try:
            status, initial = first.request("GET", "/api/state")
            self.assertEqual(200, status)
            self.assertEqual("awaiting_decision", initial["mode"])
            self.assertEqual(2, len(initial["preview"]["project_scopes"]))
            proposal_id = initial["preview"]["relationship_proposal"]["proposal_id"]
            status, decided = first.request(
                "POST",
                "/api/decide",
                {"decision": "accept", "proposal_id": proposal_id},
                first.app.token,
            )
            self.assertEqual(200, status)
            self.assertEqual("decided", decided["mode"])
            self.assertEqual("accepted", decided["report"]["relationship_proposal"]["status"])
            self.assertIsNotNone(decided["report"]["plan"])
            self.assertEqual(
                "codex_packet_test_double",
                decided["report"]["bounded_route_simulation"]["selected_route"],
            )
            self.assertEqual(4, len(decided["report"]["timeline"]))
            plan_id = decided["report"]["plan"]["plan_id"]
        finally:
            first.close()

        restarted = RunningApp(store)
        try:
            status, restored = restarted.request("GET", "/api/state")
            self.assertEqual(200, status)
            self.assertEqual("decided", restored["mode"])
            self.assertEqual(plan_id, restored["report"]["plan"]["plan_id"])
            self.assertEqual(4, len(restored["report"]["timeline"]))
        finally:
            restarted.close()

    def test_rejection_persists_blocker_without_plan_or_route(self):
        app = RunningApp(Path(self.temp.name) / "reject.jsonl")
        try:
            _, initial = app.request("GET", "/api/state")
            proposal_id = initial["preview"]["relationship_proposal"]["proposal_id"]
            status, decided = app.request(
                "POST",
                "/api/decide",
                {"decision": "reject", "proposal_id": proposal_id},
                app.app.token,
            )
            self.assertEqual(200, status)
            self.assertEqual("rejected", decided["report"]["relationship_proposal"]["status"])
            self.assertIsNone(decided["report"]["plan"])
            self.assertIsNone(decided["report"]["bounded_route_simulation"])
            self.assertEqual("blocked_before_plan", decided["report"]["verification"]["observed_result"])
            self.assertFalse(decided["report"]["external_effects"])
        finally:
            app.close()

    def test_stale_proposal_and_missing_local_token_fail_closed(self):
        app = RunningApp(Path(self.temp.name) / "stale.jsonl")
        try:
            status, value = app.request(
                "POST", "/api/decide", {"decision": "accept", "proposal_id": "stale"}
            )
            self.assertEqual(403, status)
            self.assertFalse(value.get("external_effects", False))
            status, value = app.request(
                "POST",
                "/api/decide",
                {"decision": "accept", "proposal_id": "stale"},
                app.app.token,
            )
            self.assertEqual(409, status)
            self.assertIn("stale", value["error"])
        finally:
            app.close()

    def test_rendered_shell_is_self_contained_and_security_bounded(self):
        app = RunningApp(Path(self.temp.name) / "shell.jsonl")
        try:
            status, html = app.request("GET", "/")
            self.assertEqual(200, status)
            self.assertIn("Turn scattered intent", html)
            self.assertIn("Approve next move", html)
            self.assertIn("External actions off", html)
            self.assertNotIn("https://", html)
            self.assertNotIn("__DECISION_TOKEN__", html)
            status, health = app.request("GET", "/health")
            self.assertEqual({"status": "ok", "local_only": True, "external_effects": False}, health)
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()
