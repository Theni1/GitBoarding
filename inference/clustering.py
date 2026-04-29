"""
Graph clustering for the dependency graph.

Pipeline:
  1. Extract node features from the networkx graph (pagerank, depth, ext, is_entrypoint)
  2. Run 2-layer mean aggregation (simplified GraphSAGE, no learned weights) to
     produce embeddings that capture 2-hop neighborhood structure
  3. Build a cosine similarity graph between nodes using those embeddings
  4. Run Louvain community detection on the similarity graph
  5. Return { file_path: cluster_id }

Why mean aggregation instead of a trained GNN:
  We have no labeled training data per repo — every repo is unseen at request time.
  Mean aggregation is the message-passing step of GraphSAGE with identity weights.
  It still captures neighborhood topology: two files that share similar import
  neighborhoods will get similar embeddings, which Louvain then groups together.
"""

import numpy as np
import networkx as nx
import community as community_louvain

EXT_MAP = {".py": 0, ".js": 1, ".ts": 2, ".jsx": 3, ".tsx": 4, ".go": 5, ".java": 6, ".rs": 7}
NUM_FEATURES = 4  # pagerank, depth, ext_id, is_entrypoint


def _build_feature_matrix(G: nx.DiGraph) -> tuple[np.ndarray, list[str]]:
    """Returns (F, node_list) where F is [N, NUM_FEATURES] float32."""
    nodes = list(G.nodes())
    F = np.zeros((len(nodes), NUM_FEATURES), dtype=np.float32)

    for i, node in enumerate(nodes):
        data = G.nodes[node]
        F[i, 0] = data.get("pagerank", 0.0)
        F[i, 1] = float(data.get("depth", 0))
        F[i, 2] = float(EXT_MAP.get(data.get("ext", ""), -1))
        F[i, 3] = float(data.get("is_entrypoint", False))

    # Normalize each column to [0, 1]
    for col in range(NUM_FEATURES):
        col_min, col_max = F[:, col].min(), F[:, col].max()
        if col_max > col_min:
            F[:, col] = (F[:, col] - col_min) / (col_max - col_min)

    return F, nodes


def _mean_aggregation(F: np.ndarray, adj: np.ndarray, layers: int = 2) -> np.ndarray:
    """
    Simplified GraphSAGE: for each layer, replace each node's embedding with
    the mean of itself and its neighbors. No learned weights — identity transform.
    Output captures up to `layers`-hop neighborhood structure.
    """
    H = F.copy()
    # Row-normalize adjacency (add self-loops first)
    A = adj + np.eye(adj.shape[0], dtype=np.float32)
    deg = A.sum(axis=1, keepdims=True).clip(min=1)
    A_norm = A / deg

    for _ in range(layers):
        H = A_norm @ H  # [N, F] — each node becomes mean of its neighbors

    return H


def _cosine_similarity_graph(H: np.ndarray, nodes: list[str], threshold: float = 0.85) -> nx.Graph:
    """
    Build an undirected weighted graph where nodes are connected if their
    embedding cosine similarity exceeds the threshold.
    """
    norms = np.linalg.norm(H, axis=1, keepdims=True).clip(min=1e-8)
    H_norm = H / norms
    sim = H_norm @ H_norm.T  # [N, N] cosine similarity matrix

    G_sim = nx.Graph()
    G_sim.add_nodes_from(nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if sim[i, j] >= threshold:
                G_sim.add_edge(nodes[i], nodes[j], weight=float(sim[i, j]))

    return G_sim


def cluster_graph(G: nx.DiGraph) -> dict[str, int]:
    """
    Main entry point. Takes the import graph and returns a cluster label
    per file: { file_path: cluster_id }.
    """
    if len(G.nodes) == 0:
        return {}

    nodes = list(G.nodes())
    node_idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)

    # Build adjacency matrix from the import graph
    adj = np.zeros((N, N), dtype=np.float32)
    for u, v in G.edges():
        if u in node_idx and v in node_idx:
            adj[node_idx[u], node_idx[v]] = 1.0
            adj[node_idx[v], node_idx[u]] = 1.0  # treat as undirected for aggregation

    F, nodes = _build_feature_matrix(G)
    H = _mean_aggregation(F, adj, layers=2)
    G_sim = _cosine_similarity_graph(H, nodes, threshold=0.85)

    # If the similarity graph has too few edges, fall back to the raw import graph
    if G_sim.number_of_edges() < N // 4:
        G_sim = G.to_undirected()

    partition = community_louvain.best_partition(G_sim)

    # Ensure every node has a label (isolated nodes get their own cluster)
    max_label = max(partition.values(), default=-1)
    for node in nodes:
        if node not in partition:
            max_label += 1
            partition[node] = max_label

    return partition
