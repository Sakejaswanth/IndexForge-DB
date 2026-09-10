import sys, os, json, time, struct
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

sys.path.append('./build')
sys.path.insert(0, '.')
try:
    import sqlmates_core
except ImportError:
    import python_core as sqlmates_core

try:
    import rtree_core
except ImportError:
    import python_core as rtree_core

# ── Config ────────────────────────────────────────────────────────────────────
ALL_DIMS     = [2, 5, 10, 20, 30]
MAX_RAW_DIM  = 30          # how many raw CSV features to take before PCA
TARGET_ROWS  = 99_000
NOISE_STD    = 0.01
CSV_PATH     = "Data/features_3_sec.csv"
DATA_DIR     = "data"

# The 30 raw feature columns from features_3_sec.csv (superset before PCA)
COLS_30D = [
    'tempo',
    'chroma_stft_mean', 'chroma_stft_var',
    'rms_mean', 'rms_var',
    'spectral_centroid_mean', 'spectral_centroid_var',
    'spectral_bandwidth_mean', 'spectral_bandwidth_var',
    'rolloff_mean', 'rolloff_var',
    'zero_crossing_rate_mean', 'zero_crossing_rate_var',
    'harmony_mean', 'harmony_var',
    'perceptr_mean', 'perceptr_var',
    'mfcc1_mean', 'mfcc2_mean', 'mfcc3_mean', 'mfcc4_mean',
    'mfcc5_mean', 'mfcc6_mean', 'mfcc7_mean', 'mfcc8_mean',
    'mfcc9_mean', 'mfcc10_mean', 'mfcc11_mean', 'mfcc12_mean',
    'mfcc13_mean',
]
assert len(COLS_30D) == 30

# ── Helpers ───────────────────────────────────────────────────────────────────
W = 72
def sep(title=''):
    if title:
        pad = max(W - len(title) - 4, 0)
        print(f"\n╔══ {title} {'═'*pad}╗", flush=True)
    else:
        print('╚' + '═'*(W-1) + '╝\n', flush=True)

def log(msg):
    print(f"  {msg}", flush=True)

def _resolve(df, cols):
    present = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    base = df[present].values.astype(np.float32)
    if missing:
        log(f"[WARN] {len(missing)} cols missing — synthesising")
        rng = np.random.RandomState(42)
        synth = []
        for _ in missing:
            w = rng.randn(base.shape[1]).astype(np.float32)
            w /= np.linalg.norm(w) + 1e-9
            synth.append((base @ w).reshape(-1,1))
        base = np.hstack([base] + synth)
    return base

def _augment(base, target):
    n = len(base)
    copies = target // n
    rem    = target % n
    rng    = np.random.RandomState(0)
    stds   = base.std(axis=0) + 1e-9
    parts  = [base]
    for _ in range(1, copies):
        noise = rng.randn(*base.shape).astype(np.float32)
        parts.append(base + noise * stds * NOISE_STD)
    if rem > 0:
        noise = rng.randn(rem, base.shape[1]).astype(np.float32)
        parts.append(base[:rem] + noise * stds * NOISE_STD)
    return np.vstack(parts)

def _save_bin(vectors, path):
    """Save as binary: [n_rows int32][n_cols int32][flat float32]"""
    n, d = vectors.shape
    with open(path, 'wb') as f:
        f.write(struct.pack('ii', n, d))
        f.write(vectors.astype(np.float32).tobytes())
    log(f"  Saved {n:,}×{d}D → {path}")

def _build_kd(vectors, dims, tag):
    data_db   = f"{DATA_DIR}/kdtree_99k_{dims}d_data.db"
    index_idx = f"{DATA_DIR}/kdtree_99k_{dims}d_index.idx"
    for f in [data_db, index_idx]:
        if os.path.exists(f): os.remove(f)

    n = len(vectors)
    log(f"  KD-Tree {dims}D — inserting {n:,} records …")
    t0 = time.time()
    engine = sqlmates_core.IndexEngine(data_db, index_idx, dims)
    BATCH = 5_000
    rows  = vectors.tolist()
    for start in range(0, n, BATCH):
        engine.insert_vectors(rows[start:start+BATCH])
        print(f"\r    {min(start+BATCH,n):>6,}/{n:,}", end='', flush=True)
    print()
    log(f"  insert: {time.time()-t0:.1f}s  → building index …")
    t1 = time.time()
    engine.build_index()
    log(f"  ✓ KD-Tree {dims}D ready  ({time.time()-t1:.1f}s)")

def _build_rt(vectors, dims, tag):
    data_db  = f"{DATA_DIR}/rtree_99k_{dims}d_data.db"
    tree_db  = f"{DATA_DIR}/rtree_99k_{dims}d_tree.db"
    for f in [data_db, tree_db]:
        if os.path.exists(f): os.remove(f)

    n = len(vectors)
    log(f"  R-Tree {dims}D — inserting {n:,} records …")
    t0 = time.time()
    engine = rtree_core.RTreeEngine(data_db, tree_db, dims)
    BATCH = 5_000
    rows  = vectors.tolist()
    for start in range(0, n, BATCH):
        engine.insert_vectors(rows[start:start+BATCH])
        print(f"\r    {min(start+BATCH,n):>6,}/{n:,}", end='', flush=True)
    print()
    log(f"  ✓ R-Tree {dims}D ready  ({time.time()-t0:.1f}s)  "
        f"height={engine.get_tree_height()}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found. Download GTZAN from Kaggle.")
        sys.exit(1)

    sep("STEP 1 — Load & Augment")
    df = pd.read_csv(CSV_PATH)
    n_orig = len(df)
    log(f"CSV: {n_orig:,} rows, {len(df.columns)} cols")

    raw = _resolve(df, COLS_30D)
    log(f"Raw feature matrix: {raw.shape}")

    log(f"Augmenting {n_orig:,} → {TARGET_ROWS:,} rows …")
    full = _augment(raw, TARGET_ROWS)
    log(f"Augmented: {full.shape}")
    sep()

    sep("STEP 2 — Standardise & PCA")
    mean_ = full.mean(axis=0)
    std_  = full.std(axis=0) + 1e-9
    full_std = (full - mean_) / std_

    # Fit PCA on the full 30D standardised data → enough components for 30D
    log("Fitting PCA (30 components) on standardised data …")
    t0 = time.time()
    pca = PCA(n_components=MAX_RAW_DIM, random_state=42)
    pca.fit(full_std)
    log(f"PCA fit done in {time.time()-t0:.1f}s")

    # Save PCA model params so live queries can use the same transform
    pca_meta = {
        "mean":       mean_.tolist(),
        "std":        std_.tolist(),
        "components": pca.components_.tolist(),   # shape (30, 30)
        "dims":       ALL_DIMS,
    }
    meta_path = f"{DATA_DIR}/pca_meta.json"
    with open(meta_path, 'w') as f:
        json.dump(pca_meta, f)
    log(f"PCA meta saved → {meta_path}")

    # Project all data
    full_pca = pca.transform(full_std).astype(np.float32)  # (99000, 30)
    log(f"Full PCA projected shape: {full_pca.shape}")
    sep()

    sep("STEP 3 — Save per-dim .bin files")
    for dims in ALL_DIMS:
        subset = full_pca[:, :dims]
        bin_path = f"{DATA_DIR}/pca_{dims}d.bin"
        _save_bin(subset, bin_path)
    sep()

    sep("STEP 4 — Build KD-Tree indexes")
    for dims in ALL_DIMS:
        subset = full_pca[:, :dims]
        _build_kd(subset, dims, f"99K-{dims}D")
    sep()

    sep("STEP 5 — Build R-Tree indexes")
    for dims in ALL_DIMS:
        subset = full_pca[:, :dims]
        _build_rt(subset, dims, f"99K-{dims}D")
    sep()

    log("All done. Files in data/:")
    for dims in ALL_DIMS:
        log(f"  {dims}D: pca_{dims}d.bin | kdtree_99k_{dims}d_*.db | rtree_99k_{dims}d_*.db")


if __name__ == "__main__":
    main()