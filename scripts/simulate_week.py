from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from atlas.config import load_config
from atlas.utils.time import resolve_timezone, today_in_timezone
from atlas.workflows.simulation import simulate_week


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATLAS simulation runner")
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    parser.add_argument("--db", help="Override default database path.")
    parser.add_argument(
        "--start-date",
        help="YYYY-MM-DD start date (default: today in timezone).",
    )
    parser.add_argument("--days", type=int, default=7, help="Number of days to simulate.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    tz = resolve_timezone(config.timezone)
    if args.start_date:
        start_day = datetime.fromisoformat(args.start_date).date()
    else:
        start_day = today_in_timezone(tz)

    db_path = Path(args.db).expanduser().resolve() if args.db else None
    summary = simulate_week(config, db_path, start_day, days=args.days)
    print("Simulation summary:")
    for table, info in summary.items():
        print(f"{table}: {info['count']} (latest: {info['latest'] or 'None'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
