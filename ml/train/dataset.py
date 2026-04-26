"""
PyTorch Geometric dataset for GNN training.

Each repo becomes one graph:
  - Nodes: source files, each with a feature vector
  - Edges: import relationships (file A imports file B → edge A→B)
  - Node labels: important=1 / important=0 (from consensus signal)

The dataset reads ml/data/dataset.parquet (node features + labels) and
ml/data/pagerank.parquet (used to reconstruct edges via the import graph).

Since we don't store raw edges in the parquet, edges are approximated from
file co-occurrence in the same directory + depth heuristic. For full
accuracy, re-run compute_pagerank.py with edge export enabled (see note below).

Graph per repo is a torch_geometric.data.Data object:
  x      : [num_files, NUM_FEATURES]  float32 node features
  edge_index : [2, num_edges]         long     directed edges
  y      : [num_files]                float32  labels (0 or 1)
  file_paths : list[str]              for inference / evaluation
"""

import os
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset
from torch_geometric.data import Data

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
DATASET_PATH = os.path.join(DATA_DIR, "dataset.parquet")

# Must match the normalized columns written by assemble_dataset.py
FEATURE_COLS = [
    "pagerank_score_norm",
    "contributing_score_norm",
    "first_pr_score_norm",
    "readme_score_norm",
    "unique_contributor_count_norm",
    "commit_frequency_norm",
    "file_depth",
    "file_ext_id",
    "is_entrypoint",
]

NUM_FEATURES = len(FEATURE_COLS)


def build_edges_from_paths(file_paths: list[str]) -> torch.Tensor:
    """
    Approximate edges from directory structure.

    Heuristic: files in the same directory are likely related.
    Files at depth N+1 inside a directory are connected to files at depth N in the same dir.
    This is a proxy for real import edges — good enough for training without re-fetching content.

    Returns edge_index of shape [2, num_edges].
    """
    path_to_idx = {p: i for i, p in enumerate(file_paths)}
    edges = []

    dir_to_files: dict[str, list[int]] = {}
    for path, idx in path_to_idx.items():
        parent = os.path.dirname(path)
        dir_to_files.setdefault(parent, []).append(idx)

    for siblings in dir_to_files.values():
        if len(siblings) < 2:
            continue
        # Connect each file to the first file in the directory (proxy for a shared parent)
        anchor = siblings[0]
        for sibling in siblings[1:]:
            edges.append([sibling, anchor])
            edges.append([anchor, sibling])

    if not edges:
        # Isolated graph — add self-loops so message passing doesn't crash
        self_loops = [[i, i] for i in range(len(file_paths))]
        return torch.tensor(self_loops, dtype=torch.long).t().contiguous()

    return torch.tensor(edges, dtype=torch.long).t().contiguous()


def repo_to_graph(group: pd.DataFrame) -> Data:
    file_paths = group["file_path"].tolist()

    # Node features — fill missing feature cols with 0
    feature_data = []
    for col in FEATURE_COLS:
        if col in group.columns:
            feature_data.append(group[col].fillna(0.0).values)
        else:
            feature_data.append(np.zeros(len(group)))

    x = torch.tensor(np.stack(feature_data, axis=1), dtype=torch.float)
    y = torch.tensor(group["important"].fillna(0).values, dtype=torch.float)
    edge_index = build_edges_from_paths(file_paths)

    return Data(x=x, edge_index=edge_index, y=y, file_paths=file_paths)


class RepoGraphDataset(Dataset):
    """
    One item per repo. Returns a torch_geometric Data graph.

    Usage:
        dataset = RepoGraphDataset()
        train_ds, val_ds, test_ds = dataset.split()
    """

    def __init__(self, dataset_path: str = DATASET_PATH):
        df = pd.read_parquet(dataset_path)

        # Only keep repos with enough files to be useful
        counts = df.groupby("full_name")["file_path"].count()
        valid_repos = counts[counts >= 5].index
        df = df[df["full_name"].isin(valid_repos)]

        self.graphs: list[Data] = []
        self.repo_names: list[str] = []

        print(f"Building graphs for {df['full_name'].nunique()} repos...")
        for full_name, group in df.groupby("full_name"):
            graph = repo_to_graph(group.reset_index(drop=True))
            self.graphs.append(graph)
            self.repo_names.append(full_name)

        print(f"  Built {len(self.graphs)} graphs")

    def __len__(self) -> int:
        return len(self.graphs)

    def __getitem__(self, idx: int) -> Data:
        return self.graphs[idx]

    def split(self, train: float = 0.8, val: float = 0.1, seed: int = 42):
        """
        Split into train/val/test subsets. Reproducible via seed.
        Returns three RepoGraphDataset-like objects (simple wrappers).
        """
        rng = np.random.default_rng(seed)
        indices = rng.permutation(len(self.graphs))

        n_train = int(len(indices) * train)
        n_val = int(len(indices) * val)

        train_idx = indices[:n_train]
        val_idx = indices[n_train:n_train + n_val]
        test_idx = indices[n_train + n_val:]

        return (
            _Subset(self, train_idx),
            _Subset(self, val_idx),
            _Subset(self, test_idx),
        )


class _Subset(Dataset):
    def __init__(self, parent: RepoGraphDataset, indices):
        self.parent = parent
        self.indices = indices

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        return self.parent[self.indices[idx]]
