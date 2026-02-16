"""
Course content quality metrics: ROUGE, BERTScore, and faithfulness.
Compares generated summary/notes against reference and/or source transcript.

  python course_quality_metrics.py --transcript transcript.txt --generated summary.txt [--reference ref_summary.txt]
  python course_quality_metrics.py --transcript transcript.txt --generated summary.txt --reference ref.txt --json

Optional packages: rouge-score, bert-score. Faithfulness uses simple n-gram overlap by default.
"""
import argparse
import re
import sys


def rouge_scores(generated: str, reference: str):
    """ROUGE-1, ROUGE-2, ROUGE-L (F1)."""
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
        scores = scorer.score(reference, generated)
        return {
            "rouge1_f": scores["rouge1"].fmeasure,
            "rouge2_f": scores["rouge2"].fmeasure,
            "rougeL_f": scores["rougeL"].fmeasure,
        }
    except ImportError:
        return None


def bert_score_similarity(generated: str, reference: str):
    """BERTScore F1 (semantic similarity)."""
    try:
        from bert_score import score as bert_score_fn
        P, R, F1 = bert_score_fn([generated], [reference], lang="en", verbose=False)
        return float(F1[0])
    except ImportError:
        return None
    except Exception:
        return None


def faithfulness_score(generated: str, source_transcript: str) -> float:
    """
    Simple faithfulness: fraction of non-stopword unigrams in generated that appear in source.
    Returns 0-1; higher = more claims grounded in transcript.
    """
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "to", "of", "and", "in", "that", "for", "on", "with", "as", "by",
            "this", "at", "from", "or", "it", "its", "if", "then", "so"}
    def tokens(t):
        return set(re.findall(r"\b[a-z0-9]{2,}\b", t.lower())) - stop
    gen_tok = tokens(generated)
    src_tok = tokens(source_transcript)
    if not gen_tok:
        return 1.0
    overlap = len(gen_tok & src_tok) / len(gen_tok)
    return round(min(1.0, overlap), 4)


def main():
    ap = argparse.ArgumentParser(description="Course content quality: ROUGE, BERTScore, faithfulness.")
    ap.add_argument("--transcript", "-T", required=True, help="Source transcript file (for faithfulness)")
    ap.add_argument("--generated", "-G", required=True, help="Generated summary/course content file")
    ap.add_argument("--reference", "-R", default=None, help="Reference summary file (for ROUGE/BERTScore)")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    args = ap.parse_args()

    def read_path(p: str) -> str:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()

    transcript = read_path(args.transcript)
    generated = read_path(args.generated)
    reference = read_path(args.reference) if args.reference else None

    result = {}

    # Faithfulness: generated vs source transcript (no reference needed)
    result["faithfulness"] = faithfulness_score(generated, transcript)

    if reference:
        rouge = rouge_scores(generated, reference)
        if rouge:
            result.update(rouge)
        bs = bert_score_similarity(generated, reference)
        if bs is not None:
            result["bertscore_f1"] = round(bs, 4)
    else:
        result["note"] = "No reference summary; only faithfulness computed. Add --reference for ROUGE/BERTScore."

    if args.json:
        import json
        print(json.dumps(result))
    else:
        print("Faithfulness (generated vs transcript):", result["faithfulness"])
        if "rouge1_f" in result:
            print("ROUGE-1 F1:", result["rouge1_f"])
            print("ROUGE-2 F1:", result["rouge2_f"])
            print("ROUGE-L F1:", result["rougeL_f"])
        if "bertscore_f1" in result:
            print("BERTScore F1:", result["bertscore_f1"])
        if result.get("note"):
            print(result["note"])


if __name__ == "__main__":
    main()
