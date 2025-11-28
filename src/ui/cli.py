"""Command line interface for the Nazim Hikmet crawler pipeline."""
from __future__ import annotations

import argparse
import logging

from src.zen.pipelines.crawl_pipeline import crawl_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Nazim Hikmet Digital Twin CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    crawl_parser = subparsers.add_parser("crawl", help="Run the ingestion pipeline")
    crawl_parser.add_argument("--source", action="append", dest="source_names", help="Limit run to specific sources.")
    crawl_parser.set_defaults(func=_run_crawl)

    args = parser.parse_args()
    args.func(args)


def _run_crawl(args: argparse.Namespace) -> None:
    logging.getLogger().setLevel(logging.INFO)
    run_response = crawl_pipeline(source_names=args.source_names)
    try:
        run_name = getattr(run_response, "name", None)
        run_status = getattr(run_response, "status", None)
        if run_name or run_status:
            logging.info("Pipeline run %s completed with status %s", run_name or "<unknown>", run_status or "<unknown>")
    except Exception:
        logging.debug("Pipeline run response could not be logged", exc_info=True)


if __name__ == "__main__":
    main()
