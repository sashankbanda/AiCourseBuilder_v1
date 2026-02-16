"""
Transcription accuracy metrics: WER, CER, and optional confidence from benchmark.
Requires a reference (ground truth) transcript to compute WER/CER.

  python metrics_accuracy.py --hypothesis transcript.txt --reference reference.txt
  python metrics_accuracy.py --hypothesis transcript.txt --reference reference.txt --hypothesis-is-path

Reads hypothesis and reference from files (one transcript per file, or pass text via stdin).
Uses jiwer for WER/CER. Optional: --confidence 0.85 to record avg confidence from benchmark.
"""
import argparse
import sys


def wer_cer(hypothesis: str, reference: str):
    """Compute WER and CER using jiwer."""
    try:
        import jiwer
    except ImportError:
        print("Install jiwer: pip install jiwer", file=sys.stderr)
        return None, None

    # jiwer: WER and CER on raw strings
    wer = jiwer.wer(reference, hypothesis)
    cer = jiwer.cer(reference, hypothesis)
    return wer, cer


def main():
    ap = argparse.ArgumentParser(description="Compute WER/CER between hypothesis and reference transcript.")
    ap.add_argument("--hypothesis", "-H", required=True, help="Hypothesis transcript (path or inline text)")
    ap.add_argument("--reference", "-R", required=True, help="Reference (ground truth) transcript (path or inline text)")
    ap.add_argument("--hypothesis-is-path", action="store_true", help="Treat --hypothesis as file path")
    ap.add_argument("--reference-is-path", action="store_true", help="Treat --reference as file path")
    ap.add_argument("--confidence", type=float, default=None, help="Optional: average confidence score 0-1 (e.g. from benchmark)")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    args = ap.parse_args()

    def load(s: str, is_path: bool) -> str:
        if is_path:
            with open(s, "r", encoding="utf-8") as f:
                return f.read().strip()
        return s.strip()

    hyp = load(args.hypothesis, args.hypothesis_is_path)
    ref = load(args.reference, args.reference_is_path)

    if not ref:
        print("Reference is empty.", file=sys.stderr)
        sys.exit(1)

    w, c = wer_cer(hyp, ref)
    if w is None:
        sys.exit(1)

    result = {
        "wer": round(w, 4),
        "cer": round(c, 4),
        "hypothesis_words": len(hyp.split()),
        "reference_words": len(ref.split()),
    }
    if args.confidence is not None:
        result["avg_confidence"] = round(args.confidence, 4)

    if args.json:
        import json
        print(json.dumps(result))
    else:
        print(f"WER (Word Error Rate):  {result['wer']:.4f}")
        print(f"CER (Character Error Rate): {result['cer']:.4f}")
        print(f"Reference words: {result['reference_words']}")
        if args.confidence is not None:
            print(f"Avg confidence: {result['avg_confidence']:.4f}")


if __name__ == "__main__":
    main()
