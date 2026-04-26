"""
GNN model: GraphSAGE encoder + ranking head.

Architecture:
  1. GraphSAGE layers — aggregate features from neighbouring files (imports/dir siblings)
     to build a context-aware embedding for each file
  2. Ranking head — MLP that maps each node embedding to a scalar importance score

Why GraphSAGE over GAT:
  - GraphSAGE is faster and more stable on heterogeneous graphs (our repos vary wildly in size)
  - GAT's attention weights add value when edge types are meaningful — our approximated
    directory edges aren't rich enough to justify the extra complexity yet

Output:
  - scores: [num_nodes] float — higher = more important for onboarding
  - Used with BCEWithLogitsLoss during training (binary classification per file)
  - Used as a ranking signal at inference (argsort descending)
"""

import torch
import torch.nn as nn
from torch_geometric.nn import SAGEConv

from dataset import NUM_FEATURES


class FileRanker(nn.Module):
    def __init__(
        self,
        in_channels: int = NUM_FEATURES,
        hidden_channels: int = 64,
        num_layers: int = 3,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()

        # Input → hidden
        self.convs.append(SAGEConv(in_channels, hidden_channels))
        self.bns.append(nn.BatchNorm1d(hidden_channels))

        # Hidden → hidden (num_layers - 1 additional layers)
        for _ in range(num_layers - 1):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
            self.bns.append(nn.BatchNorm1d(hidden_channels))

        # Ranking head: embedding → scalar score
        self.head = nn.Sequential(
            nn.Linear(hidden_channels, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        for conv, bn in zip(self.convs, self.bns):
            x = conv(x, edge_index)
            x = bn(x)
            x = torch.relu(x)
            x = self.dropout(x)

        # [num_nodes, 1] → [num_nodes]
        return self.head(x).squeeze(-1)
