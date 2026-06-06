"""Run the C.O.B.R.A. Chat UI standalone."""

from __future__ import annotations

import argparse

from chat_ui.config import ChatUIConfig
from chat_ui.server import ChatUIServer


def main() -> None:
    parser = argparse.ArgumentParser(description="C.O.B.R.A. Chat UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    config = ChatUIConfig(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
    )
    server = ChatUIServer(config)
    print(f"C.O.B.R.A. Chat UI at http://{config.host}:{config.port}")
    server.start(block=True)


if __name__ == "__main__":
    main()
