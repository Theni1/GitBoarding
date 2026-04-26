"""
Evaluation harness for the trained FileRanker GNN.

Metrics (all computed at k=10, i.e. top-10 predicted files):
  - NDCG@10  — primary metric. Measures ranking quality — are important files near the top?
  - Recall@10 — what fraction of truly important files appear in the top 10?
  - MRR       — mean reciprocal rank of the first relevant file (how quickly do we surface one?)

Also runs four baselines for comparison:
  - Random
  - File size proxy (file_depth inverted — shallower = likely more important)
  - PageRank alone
  - README mentions alone

Usage:
    python evaluate.py                         # evaluates best.pt on test split
    python evaluate.py --checkpoint my.pt      # evaluate a specific checkpoint
    python evaluate.py --repo facebook/react   # show predicted path for one repo
"""

import os
import sys
import argparse
import numpy as np
import torch
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from dataset import RepoGraphDataset, FEATURE_COLS
from model import FileRanker

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "../checkpoints")
K = 10


# ── Metric helpers ────────────────────────────────────────────────────────────

def dcg(relevances: np.ndarray) -> float:
    return sum(r / np.log2(i + 2) for i, r in enumerate(relevances))


def ndcg_at_k(scores: np.ndarray, labels: np.ndarray, k: int = K) -> float:
    top_k_idx = np.argsort(scores)[::-1][:k]
    ideal_idx = np.argsort(labels)[::-1][:k]
    return dcg(labels[top_k_idx]) / (dcg(labels[ideal_idx]) + 1e-9)


def recall_at_k(scores: np.ndarray, labels: np.ndarray, k: int = K) -> float:
    top_k_idx = set(np.argsort(scores)[::-1][:k])
    relevant = set(np.where(labels == 1)[0])
    if not relevant:
        return 0.0
    return len(top_k_idx & relevant) / len(relevant)


def mrr(scores: np.ndarray, labels: np.ndarray) -> float:
    ranked_idx = np.argsort(scores)[::-1]
    for rank, idx in enumerate(ranked_idx, start=1):
        if labels[idx] == 1:
            return 1.0 / rank
    return 0.0


def evaluate_graphs(model, graphs, device) -> dict:
    model.eval()
    ndcgs, recalls, mrrs = [], [], []

    with torch.no_grad():
        for graph in graphs:
            graph = graph.to(device)
            scores = model(graph.x, graph.edge_index).cpu().numpy()
            labels = graph.y.cpu().numpy()

            if labels.sum() == 0:
                continue  # skip repos with no positive labels

            ndcgs.append(ndcg_at_k(scores, labels))
            recalls.append(recall_at_k(scores, labels))
            mrrs.append(mrr(scores, labels))

    return {
        f"NDCG@{K}":   np.mean(ndcgs),
        f"Recall@{K}": np.mean(recalls),
        "MRR":          np.mean(mrrs),
        "n_repos":      len(ndcgs),
    }


# ── Baselines ─────────────────────────────────────────────────────────────────

def baseline_random(graphs) -> dict:
    ndcgs, recalls, mrrs = [], [], []
    rng = np.random.default_rng(42)
    for graph in graphs:
        labels = graph.y.numpy()
        if labels.sum() == 0:
            continue
        scores = rng.random(len(labels))
        ndcgs.append(ndcg_at_k(scores, labels))
        recalls.append(recall_at_k(scores, labels))
        mrrs.append(mrr(scores, labels))
    return {f"NDCG@{K}": np.mean(ndcgs), f"Recall@{K}": np.mean(recalls), "MRR": np.mean(mrrs)}


def baseline_single_feature(graphs, feature_name: str) -> dict:
    """Use one normalized feature column as the score."""
    idx = FEATURE_COLS.index(feature_name)
    ndcgs, recalls, mrrs = [], [], []
    for graph in graphs:
        labels = graph.y.numpy()
        if labels.sum() == 0:
            continue
        scores = graph.x[:, idx].numpy()
        ndcgs.append(ndcg_at_k(scores, labels))
        recalls.append(recall_at_k(scores, labels))
        mrrs.append(mrr(scores, labels))
    return {f"NDCG@{K}": np.mean(ndcgs), f"Recall@{K}": np.mean(recalls), "MRR": np.mean(mrrs)}


def baseline_depth(graphs) -> dict:
    """Shallower files ranked higher — naive structural heuristic."""
    idx = FEATURE_COLS.index("file_depth")
    ndcgs, recalls, mrrs = [], [], []
    for graph in graphs:
        labels = graph.y.numpy()
        if labels.sum() == 0:
            continue
        scores = -graph.x[:, idx].numpy()  # negate: lower depth = higher score
        ndcgs.append(ndcg_at_k(scores, labels))
        recalls.append(recall_at_k(scores, labels))
        mrrs.append(mrr(scores, labels))
    return {f"NDCG@{K}": np.mean(ndcgs), f"Recall@{K}": np.mean(recalls), "MRR": np.mean(mrrs)}


# ── Qualitative inspection ─────────────────────────────────────────────────────

def show_repo_prediction(model, dataset: RepoGraphDataset, repo_name: str, device, top_n: int = 10):
    try:
        idx = dataset.repo_names.index(repo_name)
    except ValueError:
        print(f"Repo '{repo_name}' not found in dataset.")
        return

    graph = dataset[idx].to(device)
    model.eval()
    with torch.no_grad():
        scores = model(graph.x, graph.edge_index).cpu().numpy()

    file_paths = graph.file_paths
    labels = graph.y.cpu().numpy()
    ranked = np.argsort(scores)[::-1]

    print(f"\nPredicted onboarding path for {repo_name}:")
    print(f"{'Rank':<6} {'Score':<8} {'Label':<8} File")
    print("-" * 60)
    for rank, i in enumerate(ranked[:top_n], start=1):
        label = "✅" if labels[i] == 1 else "  "
        print(f"{rank:<6} {scores[i]:<8.3f} {label:<8} {file_paths[i]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default=os.path.join(CHECKPOINT_DIR, "best.pt"))
    p.add_argument("--repo", type=str, default=None, help="Show predicted path for one repo")
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading dataset...")
    dataset = RepoGraphDataset()
    _, val_ds, test_ds = dataset.split()
    test_graphs = [test_ds[i] for i in range(len(test_ds))]

    print(f"Loading checkpoint: {args.checkpoint}")
    ckpt = torch.load(args.checkpoint, map_location=device)
    saved_args = ckpt.get("args", {})
    model = FileRanker(
        hidden_channels=saved_args.get("hidden", 64),
        num_layers=saved_args.get("layers", 3),
        dropout=saved_args.get("dropout", 0.3),
    ).to(device)
    model.load_state_dict(ckpt["model_state"])

    if args.repo:
        show_repo_prediction(model, dataset, args.repo, device)
        return

    # Run model
    print(f"\nEvaluating on {len(test_graphs)} test repos...\n")
    gnn_metrics = evaluate_graphs(model, test_graphs, device)

    # Run baselines on same test set
    baselines = {
        "Random":          baseline_random(test_graphs),
        "Shallow files":   baseline_depth(test_graphs),
        "PageRank only":   baseline_single_feature(test_graphs, "pagerank_score_norm"),
        "README only":     baseline_single_feature(test_graphs, "readme_score_norm"),
    }

    # Print comparison table
    header = f"{'Model':<22} {'NDCG@10':>10} {'Recall@10':>12} {'MRR':>8}"
    print(header)
    print("-" * len(header))
    for name, m in baselines.items():
        print(f"{name:<22} {m[f'NDCG@{K}']:>10.4f} {m[f'Recall@{K}']:>12.4f} {m['MRR']:>8.4f}")
    print("-" * len(header))
    print(f"{'GNN (ours)':<22} {gnn_metrics[f'NDCG@{K}']:>10.4f} {gnn_metrics[f'Recall@{K}']:>12.4f} {gnn_metrics['MRR']:>8.4f}")
    print(f"\nEvaluated on {gnn_metrics['n_repos']} repos (test split)")


if __name__ == "__main__":
    main()
