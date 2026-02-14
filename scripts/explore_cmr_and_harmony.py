#!/usr/bin/env python3
"""
Explore CMR collection search and Harmony fetch (aligned with Harmony API introduction.ipynb).

Use this to:
  - Search CMR for collections by short_name or keyword (notebook pattern).
  - Verify Harmony credentials and rangeset URL format.
  - Optionally run a live fetch and grid normalization check.

Usage (from project root):
  python scripts/explore_cmr_and_harmony.py --keyword TEMPO
  python scripts/explore_cmr_and_harmony.py --short-name harmony_example --cmr-uat
  python scripts/explore_cmr_and_harmony.py --validate
  python scripts/explore_cmr_and_harmony.py --validate --live

Requires .env with BEARER_TOKEN or EARTHDATA_USERNAME + EARTHDATA_PASSWORD for --validate/--live.
"""
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Explore CMR search and Harmony ingestion")
    parser.add_argument("--short-name", help="CMR collection short_name (notebook pattern)")
    parser.add_argument("--version", type=int, help="CMR collection version")
    parser.add_argument("--keyword", help="CMR keyword search (e.g. TEMPO)")
    parser.add_argument(
        "--cmr-uat",
        action="store_true",
        help="Use CMR UAT (cmr.uat.earthdata.nasa.gov); set HARMONY_USE_UAT=1 for Harmony UAT",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run ingestion validation (token, URL format, optional live fetch)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="With --validate: perform live Harmony fetch and grid normalization",
    )
    args = parser.parse_args()

    if args.cmr_uat:
        os.environ["HARMONY_USE_UAT"] = "1"
        # Reload config so CMR_BASE_URL is UAT
        if "config" in sys.modules:
            del sys.modules["config"]
        if "services.harmony_service" in sys.modules:
            del sys.modules["services.harmony_service"]

    # CMR search (notebook: short_name + version; optional keyword)
    if args.short_name or args.keyword:
        from config import CMR_BASE_URL
        from services.harmony_service import search_cmr_collections

        print("CMR collection search")
        print("Base URL:", CMR_BASE_URL)
        entries = search_cmr_collections(
            short_name=args.short_name or None,
            version=args.version,
            keyword=args.keyword or None,
        )
        if not entries:
            print("No collections found.")
        else:
            for i, e in enumerate(entries[:20], 1):
                cid = e.get("id", "")
                title = e.get("title", "")
                sn = e.get("short_name", "")
                print(f"  {i}. {cid}  short_name={sn}")
                print(f"     {title[:80]}...")
        if len(entries) > 20:
            print(f"  ... and {len(entries) - 20} more")

    # Validation (token, URL, optional live fetch)
    if args.validate:
        if args.live:
            os.environ["INGESTION_LIVE"] = "1"
        # Delegate to existing validation script
        from tests.run_ingestion_validation import main as run_validation
        return run_validation()

    return 0


if __name__ == "__main__":
    sys.exit(main())
