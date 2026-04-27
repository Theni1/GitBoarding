"""
Loads the trained FileRanker checkpoint and runs inference.

Thin wrapper around the training model — keeps inference/ self-contained
without duplicating the architecture definition.
"""

import os
import importlib.util
import torch

import sys
import torch.nn as nn

# Load dataset module first (needed by model.py for NUM_FEATURES)
_train_dir = os.path.join(os.path.dirname(__file__), "../ml/train")
_ds_spec = importlib.util.spec_from_file_location("train_dataset", os.path.join(_train_dir, "dataset.py"))
_ds_mod = importlib.util.module_from_spec(_ds_spec)
sys.modules["dataset"] = _ds_mod
_ds_spec.loader.exec_module(_ds_mod)

# Now load model.py — its `from dataset import NUM_FEATURES` will find the module above
_spec = importlib.util.spec_from_file_location("train_model", os.path.join(_train_dir, "model.py"))
_train_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_train_model)
FileRanker = _train_model.FileRanker

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    os.path.join(os.path.dirname(__file__), "../ml/checkpoints/best.pt"),
)


def load_model(checkpoint_path: str = CHECKPOINT_PATH) -> FileRanker:
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"No checkpoint found at {checkpoint_path}. "
            "Train the model first: cd ml/train && python train.py"
        )

    ckpt = torch.load(checkpoint_path, map_location="cpu")
    saved_args = ckpt.get("args", {})

    model = FileRanker(
        hidden_channels=saved_args.get("hidden", 64),
        num_layers=saved_args.get("layers", 3),
        dropout=0.0,  # no dropout at inference
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model


@torch.no_grad()
def rank_files(model: FileRanker, x: torch.Tensor, edge_index: torch.Tensor) -> list[int]:
    """Return file indices sorted by predicted importance (highest first)."""
    scores = model(x, edge_index)
    return torch.argsort(scores, descending=True).tolist()
