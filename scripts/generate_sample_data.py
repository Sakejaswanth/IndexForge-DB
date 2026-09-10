"""
scripts/generate_sample_data.py
Generates lightweight sample indexes and metadata for demo and hosting environments.
Allows Audio Search and Image Search tabs to work immediately out-of-the-box.
"""

import os
import sys
import json
import csv
import random
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import python_core as core

ALL_DIMS = [2, 5, 10, 20, 30]
SAMPLE_COUNT = 1000

GENRES = ["blues", "classical", "country", "disco", "hiphop", "jazz", "metal", "pop", "reggae", "rock"]
DOG_BREEDS = [
    "golden retriever", "german shepherd", "labrador retriever", "french bulldog",
    "beagle", "poodle", "rottweiler", "yorkshire terrier", "boxer", "siberian husky",
    "chihuahua", "dachshund", "great dane", "doberman", "shiba inu"
]

def generate_audio_sample_data(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "features_3_sec.csv")

    print("Generating sample GTZAN audio metadata...")
    rows = []
    for i in range(SAMPLE_COUNT):
        genre = GENRES[i % len(GENRES)]
        idx = (i // len(GENRES)) % 100
        filename = f"{genre}.{idx:05d}.wav"
        rows.append({"filename": filename, "genre": genre, "tempo": 120.0})

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "genre", "tempo"])
        writer.writeheader()
        writer.writerows(rows)

    # Generate synthetic 30D PCA projections
    rng = np.random.RandomState(42)
    # Audio latent clusters per genre
    genre_centers = rng.randn(len(GENRES), 30).astype(np.float32) * 2.0
    audio_vectors = []
    for i in range(SAMPLE_COUNT):
        g_idx = i % len(GENRES)
        v = genre_centers[g_idx] + rng.randn(30).astype(np.float32) * 0.5
        audio_vectors.append(v)
    audio_matrix = np.array(audio_vectors, dtype=np.float32)

    # PCA metadata for audio
    pca_meta = {
        "mean": [float(x) for x in np.mean(audio_matrix, axis=0)],
        "std": [float(x) for x in np.std(audio_matrix, axis=0) + 1e-6],
        "components": np.eye(30).tolist(),
        "dims": ALL_DIMS,
    }
    meta_path = os.path.join(data_dir, "pca_meta.json")
    with open(meta_path, "w") as f:
        json.dump(pca_meta, f, indent=2)

    # Build per-dim indexes
    for d in ALL_DIMS:
        subset = audio_matrix[:, :d].tolist()
        # KD-Tree
        kd_data = os.path.join(data_dir, f"kdtree_99k_{d}d_data.db")
        kd_idx = os.path.join(data_dir, f"kdtree_99k_{d}d_index.idx")
        e = core.IndexEngine(kd_data, kd_idx, d)
        e.insert_vectors(subset)
        e.build_index()

        # R-Tree
        rt_data = os.path.join(data_dir, f"rtree_99k_{d}d_data.db")
        rt_tree = os.path.join(data_dir, f"rtree_99k_{d}d_tree.db")
        re = core.RTreeEngine(rt_data, rt_tree, d)
        re.insert_vectors(subset)
        print(f"  [OK] Audio {d}D indexes built ({SAMPLE_COUNT} records)")

def generate_image_sample_data(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, "images_metadata.csv")

    print("Generating sample Stanford Dogs image metadata...")
    rows = []
    for i in range(SAMPLE_COUNT):
        breed = DOG_BREEDS[i % len(DOG_BREEDS)]
        img_id = (i // len(DOG_BREEDS)) % 100
        fpath = f"Data/images/{breed.replace(' ', '_')}/{breed.replace(' ', '_')}_{img_id:04d}.jpg"
        rows.append({"record_id": str(i), "label": breed, "filepath": fpath})

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "label", "filepath"])
        writer.writeheader()
        writer.writerows(rows)

    # Generate synthetic image embeddings and PCA
    rng = np.random.RandomState(99)
    breed_centers = rng.randn(len(DOG_BREEDS), 30).astype(np.float32) * 2.5
    img_vectors = []
    for i in range(SAMPLE_COUNT):
        b_idx = i % len(DOG_BREEDS)
        v = breed_centers[b_idx] + rng.randn(30).astype(np.float32) * 0.4
        img_vectors.append(v)
    img_matrix = np.array(img_vectors, dtype=np.float32)

    # PCA metadata for images
    pca_meta = {
        "mean": [float(x) for x in rng.randn(1280) * 0.1],
        "std": [float(x) for x in np.ones(1280)],
        "components": rng.randn(30, 1280).tolist(),
        "dims": ALL_DIMS,
    }
    meta_path = os.path.join(data_dir, "pca_images_meta.json")
    with open(meta_path, "w") as f:
        json.dump(pca_meta, f, indent=2)

    # Build per-dim indexes
    for d in ALL_DIMS:
        subset = img_matrix[:, :d].tolist()
        # KD-Tree
        kd_data = os.path.join(data_dir, f"img_kdtree_{d}d_data.db")
        kd_idx = os.path.join(data_dir, f"img_kdtree_{d}d_index.idx")
        e = core.IndexEngine(kd_data, kd_idx, d)
        e.insert_vectors(subset)
        e.build_index()

        # R-Tree (skip 30D for image RT as in original benchmark)
        if d in [2, 5, 10, 20]:
            rt_data = os.path.join(data_dir, f"img_rtree_{d}d_data.db")
            rt_tree = os.path.join(data_dir, f"img_rtree_{d}d_tree.db")
            re = core.RTreeEngine(rt_data, rt_tree, d)
            re.insert_vectors(subset)
        print(f"  [OK] Image {d}D indexes built ({SAMPLE_COUNT} records)")

if __name__ == "__main__":
    generate_audio_sample_data("data")
    generate_image_sample_data("data")
    print("\n[OK] Sample demo data generated successfully in data/.")
