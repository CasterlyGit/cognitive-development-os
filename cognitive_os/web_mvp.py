from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
from typing import Any, Dict, Optional, Tuple
import webbrowser

from .project_decision_loop import (
    DecisionLoopError,
    ProjectDecisionLoop,
    ProjectDecisionManifest,
    RelationshipDecision,
)
from .store import AppendOnlyEventStore, StoreError


ROOT = Path(__file__).parents[1]
DEFAULT_MANIFEST = ROOT / "examples" / "fixtures" / "mvp_project_decision_loop.json"
ASSETS = Path(__file__).with_name("web_assets")


class LocalDecisionApp:
    def __init__(self, manifest_path: Path, store_path: Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.store_path = Path(store_path)
        value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.manifest = ProjectDecisionManifest.from_dict(value)
        self.store = AppendOnlyEventStore(self.store_path)
        self.loop = ProjectDecisionLoop(self.store)
        self.token = secrets.token_urlsafe(24)
        self.preview = self.loop.preview(self.manifest)
        self.report = self._restore_report()

    def state(self) -> Dict[str, Any]:
        return {
            "mode": "decided" if self.report else "awaiting_decision",
            "preview": self.preview,
            "report": self.report,
            "persistence": {
                "kind": "local_jsonl",
                "store_path": str(self.store_path),
                "restart_reconstructable": True,
            },
        }

    def decide(self, decision_value: str, proposal_id: str) -> Dict[str, Any]:
        if proposal_id != self.preview["relationship_proposal"]["proposal_id"]:
            raise DecisionLoopError("the proposal is stale or does not match this session")
        try:
            decision = RelationshipDecision(decision_value)
        except ValueError as exc:
            raise DecisionLoopError("decision must be approve or reject") from exc
        self.report = self.loop.run(
            self.manifest, decision, human_actor="local_demo_owner"
        )
        return self.state()

    def _restore_report(self) -> Optional[Dict[str, Any]]:
        stream_id = "mvp:%s" % self.manifest.loop_id
        decisions = [
            event
            for event in self.store.events_for(stream_id)
            if event.event_type == "mvp.relationship_decided"
        ]
        if not decisions:
            return None
        if len(decisions) != 1:
            raise DecisionLoopError("local decision history is ambiguous")
        payload = decisions[0].payload
        if payload.get("proposal_id") != self.preview["relationship_proposal"]["proposal_id"]:
            raise DecisionLoopError("persisted proposal does not match the current fixture")
        return self.loop.run(
            self.manifest,
            RelationshipDecision(payload["decision"]),
            human_actor=payload["actor"],
        )


def build_server(
    manifest_path: Path, store_path: Path, host: str = "127.0.0.1", port: int = 8765
) -> Tuple[ThreadingHTTPServer, LocalDecisionApp]:
    app = LocalDecisionApp(manifest_path, store_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "CognitiveDecisionLoop/1.0"

        def do_GET(self) -> None:
            if self.path == "/":
                html = (ASSETS / "index.html").read_text(encoding="utf-8")
                self._send_bytes(
                    HTTPStatus.OK,
                    html.replace("__DECISION_TOKEN__", app.token).encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            elif self.path == "/styles.css":
                self._send_file("styles.css", "text/css; charset=utf-8")
            elif self.path == "/app.js":
                self._send_file("app.js", "text/javascript; charset=utf-8")
            elif self.path == "/api/state":
                self._send_json(HTTPStatus.OK, app.state())
            elif self.path == "/health":
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ok", "local_only": True, "external_effects": False},
                )
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != "/api/decide":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            if self.headers.get("X-Decision-Token") != app.token:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local decision token"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 4096:
                    raise DecisionLoopError("decision request size is invalid")
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                state = app.decide(value["decision"], value["proposal_id"])
            except (DecisionLoopError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {"error": str(exc), "external_effects": False},
                )
                return
            self._send_json(HTTPStatus.OK, state)

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("decision-ui %s - %s\n" % (self.address_string(), format % args))

        def _send_file(self, name: str, content_type: str) -> None:
            self._send_bytes(HTTPStatus.OK, (ASSETS / name).read_bytes(), content_type)

        def _send_json(self, status: HTTPStatus, value: Dict[str, Any]) -> None:
            self._send_bytes(
                status,
                json.dumps(value, sort_keys=True).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    return server, app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Project Decision Loop UI.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the local UI in a browser")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server, _ = build_server(args.manifest, args.store, args.host, args.port)
    except (OSError, StoreError, DecisionLoopError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "external_effects": False}), file=sys.stderr)
        return 2
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Cognitive Development OS is ready at %s" % url, flush=True)
    print("Local decision state: %s" % args.store, flush=True)
    print("External effects: disabled", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
