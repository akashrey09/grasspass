import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from grasspass import journal
from grasspass.cli import main
from grasspass.context import build_context
from grasspass.generate import generate
from grasspass.llm import LLMConfig, LLMError, chat_json, extract_json
from datetime import datetime

GOOD_REPLY = json.dumps(
    {
        "title": "Hedge Detective",
        "intro": "Follow a hedge and see who lives in it.",
        "steps": [
            {"do": "Walk along a hedge slowly.", "minutes": 10},
            {"do": "Count the kinds of leaf you can see.", "minutes": 15},
            {"do": "Stop and listen for movement inside.", "minutes": 15},
        ],
        "notice": ["Spider webs", "Fruit or seeds", "Small birds"],
        "bring": ["Water"],
        "log_prompts": ["What lived in the hedge?"],
    }
)


class FakeModelServer:
    """A stand-in for Ollama / llama-server: same /v1/chat/completions contract."""

    def __init__(self, replies, status=200):
        outer = self
        self.replies, self.requests, self.status = list(replies), [], status

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                if outer.status != 200:
                    self.send_response(outer.status)
                    self.end_headers()
                    return
                content = outer.replies.pop(0) if outer.replies else "{}"
                data = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_ctx(minutes=40):
    return build_context(
        lat=22.3072, lon=73.1812, tz_hours=5.5, now=datetime(2026, 10, 9, 8, 0), minutes=minutes
    )


class ExtractJsonTests(unittest.TestCase):
    def test_plain_fenced_and_chatty_replies(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json('Sure! Here you go:\n{"a": 1}\nEnjoy the walk.'), {"a": 1})

    def test_garbage_raises(self):
        for bad in ("no json here", '{"a": ', ""):
            with self.assertRaises(LLMError):
                extract_json(bad)


class ClientTests(unittest.TestCase):
    def test_request_shape_and_parse(self):
        srv = FakeModelServer([GOOD_REPLY])
        self.addCleanup(srv.close)
        cfg = LLMConfig(base_url=srv.url, model="gemma3:4b", api_key="local", timeout=5)
        out = chat_json(cfg, "sys", "user")
        self.assertEqual(out["title"], "Hedge Detective")
        req = srv.requests[0]
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["auth"], "Bearer local")
        self.assertEqual(req["body"]["model"], "gemma3:4b")
        self.assertEqual(req["body"]["response_format"], {"type": "json_object"})
        self.assertEqual([m["role"] for m in req["body"]["messages"]], ["system", "user"])

    def test_connection_refused_is_not_retryable(self):
        cfg = LLMConfig(base_url="http://127.0.0.1:1/v1", timeout=2)
        with self.assertRaises(LLMError) as cm:
            chat_json(cfg, "s", "u")
        self.assertFalse(cm.exception.retryable)

    def test_http_500_is_retryable_and_404_is_not(self):
        for status, retryable in ((500, True), (404, False)):
            srv = FakeModelServer([], status=status)
            self.addCleanup(srv.close)
            with self.assertRaises(LLMError) as cm:
                chat_json(LLMConfig(base_url=srv.url, timeout=5), "s", "u")
            self.assertEqual(cm.exception.retryable, retryable)

    def test_env_config_swaps_model_and_runtime(self):
        env = {"GRASSPASS_MODEL": "qwen3:8b", "GRASSPASS_BASE_URL": "http://localhost:8080/v1"}
        with mock.patch.dict(os.environ, env):
            cfg = LLMConfig.from_env()
        self.assertEqual((cfg.model, cfg.base_url), ("qwen3:8b", "http://localhost:8080/v1"))


class GenerateTests(unittest.TestCase):
    def test_model_card_is_used_and_fitted_to_time(self):
        srv = FakeModelServer([GOOD_REPLY])
        self.addCleanup(srv.close)
        card, source, notes = generate(make_ctx(30), LLMConfig(base_url=srv.url, model="m", timeout=5))
        self.assertEqual(source, "model:m")
        self.assertEqual(card["title"], "Hedge Detective")
        self.assertEqual(sum(s["minutes"] for s in card["steps"]), 30)
        self.assertEqual(notes, [])

    def test_prompt_contains_computed_facts(self):
        srv = FakeModelServer([GOOD_REPLY])
        self.addCleanup(srv.close)
        generate(make_ctx(40), LLMConfig(base_url=srv.url, timeout=5))
        user = srv.requests[0]["body"]["messages"][1]["content"]
        self.assertIn("Minutes available: 40", user)
        self.assertIn("post-monsoon", user)
        self.assertIn("morning", user)

    def test_bad_first_reply_is_retried(self):
        srv = FakeModelServer(["I cannot do that.", GOOD_REPLY])
        self.addCleanup(srv.close)
        card, source, notes = generate(make_ctx(), LLMConfig(base_url=srv.url, model="m", timeout=5))
        self.assertEqual(source, "model:m")
        self.assertEqual(len(srv.requests), 2)
        self.assertEqual(len(notes), 1)

    def test_device_instructions_from_the_model_are_rejected_then_fall_back(self):
        sneaky = json.loads(GOOD_REPLY)
        sneaky["steps"][0]["do"] = "Open an app and identify the tree."
        srv = FakeModelServer([json.dumps(sneaky), json.dumps(sneaky)])
        self.addCleanup(srv.close)
        card, source, notes = generate(make_ctx(), LLMConfig(base_url=srv.url, timeout=5))
        self.assertEqual(source, "offline-bank")
        self.assertEqual(len(srv.requests), 2)
        self.assertTrue(any("device" in n for n in notes))

    def test_unreachable_model_falls_back_immediately(self):
        card, source, notes = generate(make_ctx(), LLMConfig(base_url="http://127.0.0.1:1/v1", timeout=2))
        self.assertEqual(source, "offline-bank")
        self.assertTrue(card["steps"])
        self.assertEqual(len(notes), 1)

    def test_offline_flag_never_touches_the_network(self):
        srv = FakeModelServer([GOOD_REPLY])
        self.addCleanup(srv.close)
        _, source, _ = generate(make_ctx(), LLMConfig(base_url=srv.url), offline=True)
        self.assertEqual(source, "offline-bank")
        self.assertEqual(srv.requests, [])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"GRASSPASS_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    BASE = ["quest", "--lat", "22.3072", "--lon", "73.1812", "--tz", "5.5", "--now", "2026-10-09 16:49", "--offline"]

    def test_quest_writes_cards_and_journal(self):
        code, out, _ = self.run_cli(*self.BASE)
        self.assertEqual(code, 0)
        self.assertIn("GRASS PASS #001", out)
        self.assertIn("Back by", out)
        cards = list((Path(self.tmp.name) / "cards").iterdir())
        self.assertEqual(sorted(p.suffix for p in cards), [".html", ".md"])
        self.assertEqual(len(journal.load()), 1)

    def test_long_request_near_sunset_is_shortened(self):
        code, out, _ = self.run_cli("quest", "--lat", "22.3072", "--lon", "73.1812", "--tz", "5.5",
                                    "--now", "2026-10-09 17:40", "--minutes", "120", "--offline")
        self.assertEqual(code, 0)
        self.assertIn("Shortened from 120", out)

    def test_missing_location_is_a_clean_error(self):
        code, _, err = self.run_cli("quest", "--offline")
        self.assertEqual(code, 2)
        self.assertIn("--lat", err)

    def test_bad_inputs_are_rejected(self):
        self.assertEqual(self.run_cli("quest", "--lat", "99", "--lon", "0", "--offline")[0], 2)
        self.assertEqual(self.run_cli(*self.BASE, "--minutes", "5")[0], 2)

    def test_saved_location_is_reused(self):
        self.run_cli(*self.BASE, "--save-location")
        code, out, _ = self.run_cli("quest", "--now", "2026-10-09 16:49", "--offline")
        self.assertEqual(code, 0)
        self.assertIn("#002", out)

    def test_done_and_stats(self):
        self.run_cli(*self.BASE)
        self.assertEqual(self.run_cli("done", "1", "--minutes", "35", "--note", "saw a kingfisher")[0], 0)
        self.assertEqual(self.run_cli("done", "99", "--minutes", "5")[0], 1)
        _, out, _ = self.run_cli("stats")
        self.assertIn("Quests completed: 1", out)
        self.assertIn("Time outside:     35 min", out)
        self.assertIn("Spent generating", out)
        self.assertNotIn("for every second", out)
        _, listing, _ = self.run_cli("list")
        self.assertIn("[x] #001", listing)

    def test_ids_increment(self):
        self.run_cli(*self.BASE)
        _, out, _ = self.run_cli(*self.BASE, "--seed", "1")
        self.assertIn("#002", out)

    def test_model_failure_is_reported_but_still_produces_a_card(self):
        argv = [a for a in self.BASE if a != "--offline"] + ["--base-url", "http://127.0.0.1:1/v1"]
        code, out, _ = self.run_cli(*argv)
        self.assertEqual(code, 0)
        self.assertIn("could not reach model server", out)
        self.assertIn("offline quest bank", out)

    def test_cli_through_a_fake_model(self):
        srv = FakeModelServer([GOOD_REPLY])
        self.addCleanup(srv.close)
        argv = [a for a in self.BASE if a != "--offline"] + ["--base-url", srv.url, "--model", "gemma3:4b"]
        code, out, _ = self.run_cli(*argv)
        self.assertEqual(code, 0)
        self.assertIn("HEDGE DETECTIVE", out)
        self.assertIn("model:gemma3:4b", out)


if __name__ == "__main__":
    unittest.main()
