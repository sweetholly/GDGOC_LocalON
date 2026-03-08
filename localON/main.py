from __future__ import annotations

import argparse
import asyncio
import logging

from app.collector import CollectorSettings, SeoulDataCollector
from app.domain import create_schema, dispose_engine


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LOCAL ON data collector")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single collection cycle and exit",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser


async def run() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    settings = CollectorSettings.from_env()

    try:
        await create_schema()
        collector = SeoulDataCollector(settings=settings)

        if args.once:
            await collector.run_once()
            return

        await collector.run_forever()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(run())
