import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from desktop.agent import Agent, Model, Turn
from desktop.tools import Workspace


class ScriptedModel:
    provider = "ollama"

    def __init__(self):
        self.count = 0
        self.calls = []

    def turn(self, messages):
        self.calls.append(messages.copy())
        self.count += 1
        if self.count == 1:
            function = {"name": "read_file", "arguments": {"path": "brief.txt"}}
        elif self.count == 2:
            text = json.loads(messages[-1]["content"])["text"]
            function = {
                "name": "write_file",
                "arguments": {"path": "summary.md", "content": "Қорытынды: " + text},
            }
        else:
            result = json.loads(messages[-1]["content"])
            return Turn(
                "Сақталды." if result.get("written") else "Өзгеріс сақталмады.",
                [],
                {"role": "assistant", "content": "done"},
            )
        return Turn(
            "",
            [
                {
                    "id": "call",
                    "name": function["name"],
                    "arguments": function["arguments"],
                }
            ],
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": function}],
            },
        )


class AgentTests(unittest.TestCase):
    def test_real_read_propose_approve_write_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "brief.txt").write_text("Budget 900")
            proposals = []
            events = []
            model = ScriptedModel()

            def approve(proposal):
                proposals.append(proposal)
                self.assertFalse((root / "summary.md").exists())
                return True

            answer = Agent(Workspace(root), model, approve, events.append).run(
                "Read brief and write a summary"
            )
            self.assertEqual(answer, "Сақталды.")
            self.assertEqual((root / "summary.md").read_text(), "Қорытынды: Budget 900")
            self.assertEqual(len(proposals), 1)
            self.assertIn("summary.md", proposals[0].preview())
            self.assertIn("Budget 900", str(model.calls[1]))
            self.assertGreaterEqual(len(events), 4)

    def test_denial_never_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "brief.txt").write_text("Budget 900")
            answer = Agent(Workspace(root), ScriptedModel(), lambda _: False).run(
                "Summarize"
            )
            self.assertFalse((root / "summary.md").exists())
            self.assertIn("сақталмады", answer)

    def test_cancel_and_unsupported_tool(self):
        cancel = threading.Event()
        cancel.set()
        model = ScriptedModel()
        with self.assertRaises(InterruptedError):
            Agent(Workspace(), model, lambda _: True, cancel=cancel).run("hello")
        self.assertEqual(model.count, 0)
        agent = Agent(Workspace(), model, lambda _: True)
        with self.assertRaises(ValueError):
            agent.execute("run_shell", {"command": "echo bad"})
        with self.assertRaises(ValueError):
            agent.execute("read_file", {"path": "x", "extra": "bad"})

    def test_ollama_tool_protocol_over_real_local_http(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(
                    json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                )
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "list_directory",
                                            "arguments": {"path": "."},
                                        }
                                    }
                                ],
                            }
                        }
                    ).encode()
                )

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch("ai_core.OLLAMA_URL", f"http://127.0.0.1:{server.server_port}"):
                turn = Model("ollama", "qwen3:4b").turn(
                    [{"role": "user", "content": "list files"}]
                )
            self.assertEqual(turn.calls[0]["name"], "list_directory")
            self.assertEqual(turn.calls[0]["arguments"], {"path": "."})
            self.assertTrue(requests[0]["tools"])
            self.assertFalse(requests[0]["stream"])
            self.assertEqual(requests[0]["model"], "qwen3:4b")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class OpenAIToolTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_openai_tool_call_ids_round_trip(self, client):
        from types import SimpleNamespace as NS

        instance = client.return_value.__enter__.return_value
        call = NS(
            id="tool-id-1", function=NS(name="list_directory", arguments='{"path":"."}')
        )
        instance.chat.completions.create.side_effect = [
            NS(choices=[NS(message=NS(content=None, tool_calls=[call]))]),
            NS(choices=[NS(message=NS(content="Files listed.", tool_calls=[]))]),
        ]
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "brief.txt").write_text("brief")
            answer = Agent(
                Workspace(root),
                Model("openai", "test", "test-only-key"),
                lambda _: False,
            ).run("List files")
        self.assertEqual(answer, "Files listed.")
        second = instance.chat.completions.create.call_args_list[1].kwargs["messages"]
        self.assertEqual(second[-1]["role"], "tool")
        self.assertEqual(second[-1]["tool_call_id"], "tool-id-1")
        self.assertIn("brief.txt", second[-1]["content"])

    def test_cancel_during_review_never_writes(self):
        with tempfile.TemporaryDirectory() as root:
            cancel = threading.Event()

            def approve(_):
                cancel.set()
                return True

            agent = Agent(Workspace(root), ScriptedModel(), approve, cancel=cancel)
            result = agent.execute("write_file", {"path": "new.txt", "content": "new"})
            self.assertFalse(result["written"])
            self.assertFalse((Path(root) / "new.txt").exists())
