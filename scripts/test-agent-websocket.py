#!/usr/bin/env python3
"""Smoke-test a live agent turn and its ACLI integration over WebSocket."""

import argparse
import asyncio
import json
import urllib.request

import websockets


def create_session(base_url: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/api/v1/agents/sessions",
        data=json.dumps({"title": "ACLI WebSocket smoke test"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["id"]


async def test_interaction(base_url: str, timeout: float, require_authenticated: bool) -> None:
    session_id = await asyncio.to_thread(create_session, base_url)
    ws_url = base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    ws_url += f"/api/v1/agents/sessions/{session_id}/ws"
    expected_handshake = ["session", "history.start", "history.end", "session.ready"]

    async with websockets.connect(ws_url) as websocket:
        for expected in expected_handshake:
            frame = json.loads(await asyncio.wait_for(websocket.recv(), timeout=timeout))
            if frame.get("object") != expected:
                raise RuntimeError(f"Expected {expected!r}, received: {frame}")

        await websocket.send(
            json.dumps(
                {
                    "command": "prompt",
                    "prompt": (
                        'Use the acli tool with args ["jira", "auth", "status"]. '
                        "Report whether ACLI is installed and authenticated, based only on the tool result."
                    ),
                }
            )
        )

        acli_result = None
        while True:
            frame = json.loads(await asyncio.wait_for(websocket.recv(), timeout=timeout))
            if frame.get("object") in {"agent.error", "command.rejected"}:
                raise RuntimeError(f"Agent interaction failed: {frame}")
            event = frame.get("event", {})
            event_type = event.get("type")
            if event_type == "tool.completed" and event.get("payload", {}).get("tool") == "acli":
                acli_result = event["payload"]["result"]
                print(f"ACLI tool result: {json.dumps(acli_result, sort_keys=True)}")
            if event.get("type") == "turn.completed":
                if acli_result is None:
                    raise RuntimeError("Agent completed without invoking ACLI")
                if require_authenticated and acli_result.get("exit_code") != 0:
                    raise RuntimeError(f"ACLI is not authenticated: {acli_result}")
                text = event.get("payload", {}).get("text", "")
                if not text:
                    raise RuntimeError("Agent completed without a response")
                print(f"WebSocket ACLI smoke test passed for session {session_id}")
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8888")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--require-authenticated",
        action="store_true",
        help="fail unless 'acli jira auth status' succeeds",
    )
    args = parser.parse_args()
    asyncio.run(test_interaction(args.base_url.rstrip("/"), args.timeout, args.require_authenticated))


if __name__ == "__main__":
    main()
