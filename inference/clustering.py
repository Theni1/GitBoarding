import networkx as nx
import community as community_louvain


def _shared_prefix_depth(a: str, b: str) -> int:
    parts_a = a.split("/")[:-1]  # exclude filename
    parts_b = b.split("/")[:-1]
    depth = 0
    for x, y in zip(parts_a, parts_b):
        if x == y:
            depth += 1
        else:
            break
    return depth


def _build_similarity_graph(G: nx.DiGraph) -> nx.Graph:
    nodes = list(G.nodes())
    import_edges = set(G.edges())

    G_sim = nx.Graph()
    G_sim.add_nodes_from(nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            weight = 0.0

            depth = _shared_prefix_depth(a, b)
            if depth >= 3:
                weight += 3.0
            elif depth == 2:
                weight += 2.0
            elif depth == 1:
                weight += 0.5  # weak signal — same top-level dir only

            if (a, b) in import_edges or (b, a) in import_edges:
                weight += 1.5

            if weight > 0:
                G_sim.add_edge(a, b, weight=weight)

    return G_sim


def cluster_graph(G: nx.DiGraph) -> dict[str, int]:
    if len(G.nodes) == 0:
        return {}

    nodes = list(G.nodes())
    G_sim = _build_similarity_graph(G)

    # Fall back to raw undirected import graph if similarity graph is too sparse
    if G_sim.number_of_edges() < len(nodes) // 4:
        G_sim = G.to_undirected()

    partition = community_louvain.best_partition(G_sim)

    # Isolated nodes get their own cluster
    max_label = max(partition.values(), default=-1)
    for node in nodes:
        if node not in partition:
            max_label += 1
            partition[node] = max_label

    # Merge clusters smaller than 3 into the nearest cluster by shared edges
    MIN_CLUSTER_SIZE = 3
    cluster_sizes: dict[int, int] = {}
    for label in partition.values():
        cluster_sizes[label] = cluster_sizes.get(label, 0) + 1

    large_clusters = [l for l, size in cluster_sizes.items() if size >= MIN_CLUSTER_SIZE]

    if large_clusters:
        for node, label in list(partition.items()):
            if cluster_sizes[label] < MIN_CLUSTER_SIZE:
                # Find the large cluster this node shares the most edges with
                neighbor_counts: dict[int, int] = {}
                for neighbor in G_sim.neighbors(node):
                    nl = partition[neighbor]
                    if nl in cluster_sizes and cluster_sizes[nl] >= MIN_CLUSTER_SIZE:
                        neighbor_counts[nl] = neighbor_counts.get(nl, 0) + 1

                if neighbor_counts:
                    partition[node] = max(neighbor_counts, key=lambda l: neighbor_counts[l])
                else:
                    partition[node] = large_clusters[0]

    return partition
