"""
Command-line interface (CLI) for generating synthetic corpora (§9).

Usage:
    python -m data.cli --seed 7 --scale small --out corpus/
    python -m data.cli --seed 7 --scale medium --parquet --out corpus/
    python -m data.cli --verify-determinism
"""

from __future__ import annotations

import argparse
import sys

from .config import CorpusConfig
from .generator import StreamingCorpusGenerator
from .verify import verify_determinism


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Breadcrumbs Synthetic Compliance Corpus Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--seed", type=int, default=7, help="RNG seed for deterministic generation")
    parser.add_argument(
        "--scale",
        type=str,
        default="small",
        choices=["small", "medium", "large"],
        help="Corpus scale (small ~20k docs, medium ~200k docs, large ~1M docs)",
    )
    parser.add_argument("--docs", type=int, default=None, help="Explicit total document count override")
    parser.add_argument("--out", type=str, default="corpus", help="Output directory path")
    parser.add_argument("--anomaly-rate", type=float, default=0.04, help="Base anomaly injection rate")
    parser.add_argument("--parquet", action="store_true", help="Also emit Parquet format shards")
    parser.add_argument(
        "--verify-determinism",
        action="store_true",
        help="Run determinism verification check and exit",
    )

    args = parser.parse_args()

    if args.verify_determinism:
        ok = verify_determinism(seed=args.seed)
        sys.exit(0 if ok else 1)

    config = CorpusConfig(
        seed=args.seed,
        scale=args.scale,
        total_docs=args.docs,
        output_dir=args.out,
        anomaly_rate=args.anomaly_rate,
        output_parquet=args.parquet,
    )

    config.print_summary()

    generator = StreamingCorpusGenerator(config)
    result = generator.generate_corpus()

    print("\nGeneration completed successfully!")
    print(f"Total Documents:  {result['total_documents']:,}")
    print(f"Total Anomalous:  {result['total_anomalous']:,} ({result['anomaly_rate']:.2%})")
    print(f"Elapsed Time:     {result['elapsed_seconds']:.2f} seconds")
    print(f"Output Location:  {result['output_dir']}")


if __name__ == "__main__":
    main()
