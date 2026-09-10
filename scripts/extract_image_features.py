import numpy as np
import json
import os
import sys

IMG_SIZE = (224, 224)

# ── Module-level model cache (loaded once per uvicorn process) ────────────────
_model      = None   # the feature extractor (TF or Torch)
_use_tf     = None   # True=TF, False=Torch, None=not loaded yet


def _get_model():

    global _model, _use_tf
    if _use_tf is not None:
        return  # already loaded

    # ── Try TensorFlow first ──────────────────────────────────────────────────
    try:
        import tensorflow as tf
        from tensorflow.keras.applications import MobileNetV2
        m = MobileNetV2(weights='imagenet', include_top=False,
                        pooling='avg', input_shape=(224, 224, 3))
        m.trainable = False
        _model  = m
        _use_tf = True
        return
    except Exception:
        pass

    # ── PyTorch fallback ──────────────────────────────────────────────────────
    try:
        import torch
        import torch.nn as nn

        try:
            from torchvision.models import mobilenet_v2, MobileNet_V2_Weights
            base = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
        except (ImportError, AttributeError):

            from torchvision.models import mobilenet_v2
            base = mobilenet_v2(pretrained=True)

        class MobileNetFeatures(nn.Module):
            def __init__(self, base):
                super().__init__()
                self.features = base.features
                self.pool = nn.AdaptiveAvgPool2d((1, 1))

            def forward(self, x):
                x = self.features(x)          # (B, 1280, 7, 7)
                x = self.pool(x)              # (B, 1280, 1, 1)
                return x.flatten(1)           # (B, 1280)

        _model  = MobileNetFeatures(base).eval()
        _use_tf = False
        return

    except Exception as e:
        raise RuntimeError(
            f"Cannot load MobileNetV2. Install tensorflow or torch+torchvision. Error: {e}"
        )


def extract_raw_features(image_path: str) -> np.ndarray:

    _get_model()

    if _use_tf:
        from tensorflow.keras.preprocessing import image as kimage
        from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
        img  = kimage.load_img(image_path, target_size=IMG_SIZE)
        arr  = kimage.img_to_array(img)
        batch = preprocess_input(np.expand_dims(arr, 0))
        feat  = _model.predict(batch, verbose=0)   # (1, 1280)
        return feat[0]

    else:
        import torch
        import torchvision.transforms as T
        from PIL import Image

        transform = T.Compose([
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        img   = Image.open(image_path).convert('RGB')
        batch = transform(img).unsqueeze(0)        # (1, 3, 224, 224)
        with torch.no_grad():
            feat = _model(batch).numpy()           # (1, 1280)
        return feat[0]


def project_with_pca(raw_feat: np.ndarray, pca_meta: dict, target_dim: int) -> list:

    mean_ = np.array(pca_meta["mean"],       dtype=np.float32)  # (1280,)
    std_  = np.array(pca_meta["std"],        dtype=np.float32)  # (1280,)
    comp  = np.array(pca_meta["components"], dtype=np.float32)  # (max_dim, 1280)

    std_vec   = (raw_feat.astype(np.float32) - mean_) / std_    # (1280,)
    projected = std_vec @ comp.T                                  # (max_dim,)
    return projected[:target_dim].tolist()


def extract_for_all_dims(image_path: str, pca_meta: dict, dims: list) -> dict:

    raw = extract_raw_features(image_path)
    return {d: project_with_pca(raw, pca_meta, d) for d in dims}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_image_features.py <image_file>")
        sys.exit(1)

    path      = sys.argv[1]
    meta_path = "data/pca_images_meta.json"

    if not os.path.exists(meta_path):
        print(f"ERROR: {meta_path} not found. Run preprocess_images.py first.")
        sys.exit(1)

    with open(meta_path) as f:
        meta = json.load(f)

    print(f"Extracting features from: {path}")
    raw = extract_raw_features(path)
    print(f"Feature vector: shape={raw.shape}  mean={raw.mean():.4f}  std={raw.std():.4f}")

    print("\nPCA projections:")
    for d in meta.get("dims", [2, 5, 10, 20, 30]):
        vec = project_with_pca(raw, meta, d)
        tail = "..." if d > 4 else ""
        print(f"  {d}D: {[f'{v:.3f}' for v in vec[:4]]}{tail}")