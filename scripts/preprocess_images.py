import sys, os, json, time, csv
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.setrecursionlimit(50_000)   # belt-and-suspenders for any Python recursion

# ── Config ────────────────────────────────────────────────────────────────────
IMAGE_DIR     = "Data/images"
DATA_DIR      = "data"
ALL_DIMS      = [2, 5, 10, 20, 30]
RT_DIMS       = [2, 5, 10, 20]
MAX_PER_CLASS = 100
IMG_SIZE      = (224, 224)
BATCH_SIZE    = 32

RT_INSERT_BATCH = 100

sys.path.append('./build')
import sqlmates_core
try:
    import rtree_core
    RTREE_AVAILABLE = True
except ImportError:
    RTREE_AVAILABLE = False

W = 72
def sep(t=''):
    if t: print(f"\n╔══ {t} {'═'*max(W-len(t)-4,0)}╗", flush=True)
    else: print('╚'+'═'*(W-1)+'╝\n', flush=True)
def log(m): print(f"  {m}", flush=True)

def extract_features():
    USE_TF = False
    try:
        import tensorflow as tf
        from tensorflow.keras.applications import MobileNetV2
        from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
        from tensorflow.keras.preprocessing import image as kimage
        USE_TF = True
    except ImportError:
        pass

    if not USE_TF:
        try:
            import torch
            import torchvision.transforms as T
            from torchvision.models import mobilenet_v2, MobileNet_V2_Weights
            from PIL import Image
        except ImportError:
            print("ERROR: Install tensorflow or torch+torchvision+pillow")
            sys.exit(1)

    image_root = Path(IMAGE_DIR)
    if not image_root.exists():
        print(f"\nERROR: {IMAGE_DIR} not found.")
        print("Download: kaggle datasets download -d jessicali9530/stanford-dogs-dataset")
        print("Then extract images into Data/images/<breed>/*.jpg")
        sys.exit(1)

    log("Scanning for images …")
    imgs_by_class = defaultdict(list)
    for ext in ['*.jpg','*.jpeg','*.png','*.JPG','*.JPEG','*.PNG']:
        for p in image_root.rglob(ext):
            imgs_by_class[p.parent.name].append(p)

    if not imgs_by_class:
        print(f"\nERROR: No images found in {IMAGE_DIR}")
        sys.exit(1)

    image_paths, labels, class_names = [], [], []
    for cls_name, imgs in sorted(imgs_by_class.items()):
        # "n02085620-Chihuahua" → "Chihuahua"
        clean = cls_name.split('-',1)[-1].replace('_',' ') if '-' in cls_name else cls_name.replace('_',' ')
        if clean not in class_names:
            class_names.append(clean)
        for p in sorted(imgs)[:MAX_PER_CLASS]:
            image_paths.append(str(p))
            labels.append(clean)

    N = len(image_paths)
    log(f"Found {len(imgs_by_class)} classes, {N} images total")

    if USE_TF:
        sep("Extracting CNN features (TensorFlow MobileNetV2)")
        model = MobileNetV2(weights='imagenet', include_top=False,
                            pooling='avg', input_shape=(224,224,3))
        model.trainable = False
        features = []
        for i in range(0, N, BATCH_SIZE):
            batch_imgs = []
            for p in image_paths[i:i+BATCH_SIZE]:
                try:
                    img = kimage.load_img(p, target_size=IMG_SIZE)
                    batch_imgs.append(kimage.img_to_array(img))
                except Exception:
                    batch_imgs.append(np.zeros((224,224,3), dtype=np.float32))
            feats = model.predict(preprocess_input(np.stack(batch_imgs)), verbose=0)
            features.append(feats)
            print(f"\r  {min(i+BATCH_SIZE,N)}/{N}", end='', flush=True)
        print()
        features = np.vstack(features).astype(np.float32)
    else:
        sep("Extracting CNN features (PyTorch MobileNetV2)")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        log(f"Device: {device}")

        import torch.nn as nn
        base = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)

        class MobileNetFeatures(nn.Module):
            def __init__(self, b):
                super().__init__()
                self.features = b.features
                self.pool = nn.AdaptiveAvgPool2d((1, 1))
            def forward(self, x):
                x = self.features(x)    # (B, 1280, 7, 7)
                x = self.pool(x)        # (B, 1280, 1, 1)
                return x.flatten(1)     # (B, 1280)

        model = MobileNetFeatures(base).to(device).eval()
        transform = T.Compose([
            T.Resize(256), T.CenterCrop(224), T.ToTensor(),
            T.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
        ])
        features = []
        with torch.no_grad():
            for i in range(0, N, BATCH_SIZE):
                batch = []
                for p in image_paths[i:i+BATCH_SIZE]:
                    try:
                        batch.append(transform(Image.open(p).convert('RGB')))
                    except Exception:
                        batch.append(torch.zeros(3,224,224))
                feat = model(torch.stack(batch).to(device)).cpu().numpy()
                features.append(feat)
                print(f"\r  {min(i+BATCH_SIZE,N)}/{N}", end='', flush=True)
        print()
        features = np.vstack(features).astype(np.float32)

    log(f"Feature matrix: {features.shape}")
    return features, image_paths, labels

# ── Step 2: PCA ───────────────────────────────────────────────────────────────
def run_pca(features):
    from sklearn.decomposition import PCA
    sep("PCA reduction")
    mean_ = features.mean(axis=0)
    std_  = features.std(axis=0) + 1e-9
    std_f = (features - mean_) / std_

    max_dim = max(ALL_DIMS)
    log(f"Fitting PCA({max_dim}) on {features.shape[0]:,} × {features.shape[1]:,} …")
    t0 = time.time()
    pca = PCA(n_components=max_dim, random_state=42)
    pca.fit(std_f)
    log(f"PCA done in {time.time()-t0:.1f}s")

    projected = pca.transform(std_f).astype(np.float32)

    meta = {
        "mean":       mean_.tolist(),
        "std":        std_.tolist(),
        "components": pca.components_.tolist(),
        "dims":       ALL_DIMS,
    }
    meta_path = f"{DATA_DIR}/pca_images_meta.json"
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
    log(f"PCA meta → {meta_path}")
    return projected

# ── Step 3: Save metadata ─────────────────────────────────────────────────────
def save_metadata(image_paths, labels):
    meta_csv = f"{DATA_DIR}/images_metadata.csv"
    with open(meta_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(["record_id","filepath","label"])
        for i,(p,l) in enumerate(zip(image_paths, labels)):
            w.writerow([i, p, l])
    log(f"Metadata → {meta_csv}  ({len(image_paths):,} rows)")

# ── Step 4: KD-Tree ───────────────────────────────────────────────────────────
def build_kd(vectors, dims):
    data_db   = f"{DATA_DIR}/img_kdtree_{dims}d_data.db"
    index_idx = f"{DATA_DIR}/img_kdtree_{dims}d_index.idx"
    for f in [data_db, index_idx]:
        if os.path.exists(f): os.remove(f)
    n = len(vectors)
    log(f"KD-Tree {dims}D — {n:,} vectors …")
    t0 = time.time()
    e = sqlmates_core.IndexEngine(data_db, index_idx, dims)
    rows = vectors.tolist()
    BATCH = 2_000
    for start in range(0, n, BATCH):
        e.insert_vectors(rows[start:start+BATCH])
        print(f"\r    {min(start+BATCH,n):>6,}/{n:,}", end='', flush=True)
    print()
    e.build_index()
    log(f"  ✓ KD {dims}D — {time.time()-t0:.1f}s  {e.get_total_records():,} records")

# ── Step 5: R-Tree (only for RT_DIMS, small batches) ─────────────────────────
def build_rt(vectors, dims):

    data_db = f"{DATA_DIR}/img_rtree_{dims}d_data.db"
    tree_db = f"{DATA_DIR}/img_rtree_{dims}d_tree.db"
    for f in [data_db, tree_db]:
        if os.path.exists(f): os.remove(f)
    n = len(vectors)
    log(f"R-Tree {dims}D — {n:,} vectors (batch={RT_INSERT_BATCH}) …")
    t0 = time.time()
    try:
        e = rtree_core.RTreeEngine(data_db, tree_db, dims)
        rows = vectors.tolist()
        for start in range(0, n, RT_INSERT_BATCH):
            chunk = rows[start:start+RT_INSERT_BATCH]
            e.insert_vectors(chunk)
            print(f"\r    {min(start+RT_INSERT_BATCH,n):>6,}/{n:,}", end='', flush=True)
        print()
        log(f"  ✓ RT {dims}D — {time.time()-t0:.1f}s  h={e.get_tree_height()}")
    except MemoryError as me:
        log(f"  ⚠ RT {dims}D MemoryError — skipping ({me})")
    except Exception as ex:
        log(f"  ⚠ RT {dims}D failed — {ex}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    sep("IMAGE PREPROCESSING — Stanford Dogs")
    features, image_paths, labels = extract_features()
    projected = run_pca(features)
    save_metadata(image_paths, labels)

    sep("Building KD-Tree indexes (all dims)")
    for dims in ALL_DIMS:
        build_kd(projected[:, :dims], dims)

    if RTREE_AVAILABLE:
        sep(f"Building R-Tree indexes (dims {RT_DIMS} only — 30D skipped to avoid segfault)")
        for dims in RT_DIMS:
            build_rt(projected[:, :dims], dims)
        log(f"  Note: R-Tree 30D intentionally skipped (degrades to worse-than-linear at 30D)")
    else:
        log("⚠ rtree_core not compiled — skipping R-Tree builds")

    sep()
    log("Done! Files in data/:")
    log(f"  pca_images_meta.json   images_metadata.csv")
    for dims in ALL_DIMS:
        kd_ok = os.path.exists(f"{DATA_DIR}/img_kdtree_{dims}d_data.db")
        rt_ok = os.path.exists(f"{DATA_DIR}/img_rtree_{dims}d_data.db")
        log(f"  {dims}D: KD={'✓' if kd_ok else '✗'}  RT={'✓' if rt_ok else '— (skipped)' if dims == 30 else '✗'}")

if __name__ == "__main__":
    main()