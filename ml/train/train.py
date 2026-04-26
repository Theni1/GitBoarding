"""
Training loop for the FileRanker GNN.

Trains on per-repo graphs, one graph at a time (no batching across repos since
graph sizes vary wildly). Uses BCEWithLogitsLoss — binary classification per file.

Logs to Weights & Biases if available, otherwise prints to stdout.

Usage:
    python train.py                        # train with defaults
    python train.py --epochs 50 --lr 3e-4  # override hyperparams

Saves best checkpoint (by val loss) to ml/checkpoints/best.pt
"""

import os
import sys
import argparse
import torch
import torch.nn as nn
from torch_geometric.data import Data

sys.path.insert(0, os.path.dirname(__file__))
from dataset import RepoGraphDataset
from model import FileRanker

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "../checkpoints")

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs",      type=int,   default=30)
    p.add_argument("--lr",          type=float, default=1e-3)
    p.add_argument("--hidden",      type=int,   default=64)
    p.add_argument("--layers",      type=int,   default=3)
    p.add_argument("--dropout",     type=float, default=0.3)
    p.add_argument("--pos-weight",  type=float, default=5.0,
                   help="Upweight positive (important) files — they're the minority class")
    p.add_argument("--wandb",       action="store_true")
    p.add_argument("--run-name",    type=str,   default="gitboarding-gnn")
    return p.parse_args()


def train_epoch(model, graphs, optimizer, loss_fn, device):
    model.train()
    total_loss = 0.0

    for graph in graphs:
        graph = graph.to(device)
        optimizer.zero_grad()
        scores = model(graph.x, graph.edge_index)
        loss = loss_fn(scores, graph.y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    return total_loss / len(graphs)


@torch.no_grad()
def eval_epoch(model, graphs, loss_fn, device):
    model.eval()
    total_loss = 0.0

    for graph in graphs:
        graph = graph.to(device)
        scores = model(graph.x, graph.edge_index)
        total_loss += loss_fn(scores, graph.y).item()

    return total_loss / len(graphs)


def main():
    args = parse_args()
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    if args.wandb and WANDB_AVAILABLE:
        wandb.init(project="gitboarding", name=args.run_name, config=vars(args))

    # Load dataset and split
    print("\nLoading dataset...")
    dataset = RepoGraphDataset()
    train_ds, val_ds, test_ds = dataset.split()
    print(f"Split: {len(train_ds)} train / {len(val_ds)} val / {len(test_ds)} test repos")

    # Collect graphs into plain lists for simple iteration
    train_graphs = [train_ds[i] for i in range(len(train_ds))]
    val_graphs   = [val_ds[i]   for i in range(len(val_ds))]

    model = FileRanker(
        hidden_channels=args.hidden,
        num_layers=args.layers,
        dropout=args.dropout,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5
    )

    # Upweight important files — they're ~10% of rows; without this the model
    # learns to predict everything as unimportant and still gets low loss
    pos_weight = torch.tensor([args.pos_weight], device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_val_loss = float("inf")
    best_epoch = 0

    print(f"\nTraining for {args.epochs} epochs...\n")
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_graphs, optimizer, loss_fn, device)
        val_loss   = eval_epoch(model, val_graphs, loss_fn, device)
        scheduler.step(val_loss)

        print(f"Epoch {epoch:3d} | train {train_loss:.4f} | val {val_loss:.4f}")

        if args.wandb and WANDB_AVAILABLE:
            wandb.log({"train_loss": train_loss, "val_loss": val_loss, "epoch": epoch})

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "args": vars(args),
            }, os.path.join(CHECKPOINT_DIR, "best.pt"))
            print(f"           ↳ saved best checkpoint")

    print(f"\nDone. Best val loss {best_val_loss:.4f} at epoch {best_epoch}")
    print(f"Checkpoint saved to {CHECKPOINT_DIR}/best.pt")

    if args.wandb and WANDB_AVAILABLE:
        wandb.finish()


if __name__ == "__main__":
    main()
