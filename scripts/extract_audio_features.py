import librosa
import numpy as np
import json
import os
import sys



FEATURE_NAMES_30 = [
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
assert len(FEATURE_NAMES_30) == 30


def extract_raw_30(audio_path: str) -> list:
    y, sr = None, None
    try:
        y, sr = librosa.load(audio_path, duration=30, sr=22050)
    except Exception:
        try:
            import soundfile as sf
            data, sr_orig = sf.read(audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            y = data.astype(np.float32)
            if sr_orig != 22050:
                y = librosa.resample(y, orig_sr=sr_orig, target_sr=22050)
            sr = 22050
            if len(y) > 30 * sr:
                y = y[:30 * sr]
        except Exception as e:
            raise ValueError(f"Could not load audio file: {e}")

    tempo, _    = librosa.beat.beat_track(y=y, sr=sr)
    chroma      = librosa.feature.chroma_stft(y=y, sr=sr)
    rms         = librosa.feature.rms(y=y)
    centroid    = librosa.feature.spectral_centroid(y=y, sr=sr)
    bandwidth   = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    rolloff     = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr         = librosa.feature.zero_crossing_rate(y)
    mfcc        = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    y_harm      = librosa.effects.harmonic(y)
    y_perc      = librosa.effects.percussive(y)

    feats = [
        float(np.squeeze(tempo)),          # tempo
        float(np.mean(chroma)),            # chroma_stft_mean
        float(np.var(chroma)),             # chroma_stft_var
        float(np.mean(rms)),               # rms_mean
        float(np.var(rms)),                # rms_var
        float(np.mean(centroid)),          # spectral_centroid_mean
        float(np.var(centroid)),           # spectral_centroid_var
        float(np.mean(bandwidth)),         # spectral_bandwidth_mean
        float(np.var(bandwidth)),          # spectral_bandwidth_var
        float(np.mean(rolloff)),           # rolloff_mean
        float(np.var(rolloff)),            # rolloff_var
        float(np.mean(zcr)),               # zero_crossing_rate_mean
        float(np.var(zcr)),                # zero_crossing_rate_var
        float(np.mean(y_harm)),            # harmony_mean
        float(np.var(y_harm)),             # harmony_var
        float(np.mean(y_perc)),            # perceptr_mean
        float(np.var(y_perc)),             # perceptr_var
    ]
    for i in range(13):
        feats.append(float(np.mean(mfcc[i])))  # mfcc1_mean … mfcc13_mean

    assert len(feats) == 30, f"Expected 30, got {len(feats)}"
    return feats


def project_with_pca(raw_30: list, pca_meta: dict, target_dim: int) -> list:

    raw = np.array(raw_30, dtype=np.float32)
    mean_ = np.array(pca_meta["mean"], dtype=np.float32)
    std_  = np.array(pca_meta["std"],  dtype=np.float32)
    comp  = np.array(pca_meta["components"], dtype=np.float32)  # (30, 30)

    standardised = (raw - mean_) / std_
    projected    = standardised @ comp.T   # (30,) @ (30, 30).T → (30,)
    return projected[:target_dim].tolist()


def extract_for_all_dims(audio_path: str, pca_meta: dict, dims: list) -> dict:

    raw_30 = extract_raw_30(audio_path)
    result = {}
    for d in dims:
        result[d] = project_with_pca(raw_30, pca_meta, d)
    return result


# ── Legacy compat ─────────────────────────────────────────────────────────────
# Keep old names so any existing imports don't break immediately.
ALL_DIMS = [2, 5, 10, 20, 30]
ALL_FEATURE_NAMES = {d: [f"pca_{i+1}" for i in range(d)] for d in ALL_DIMS}

# Feature names for the raw 30D (for display only)
FEATURE_NAMES = FEATURE_NAMES_30


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_audio_features.py <audio_file>")
        sys.exit(1)

    path = sys.argv[1]
    meta_path = "data/pca_meta.json"

    print(f"Extracting raw 30D features from: {path}")
    raw = extract_raw_30(path)
    for name, val in zip(FEATURE_NAMES_30, raw):
        print(f"  {name:<32} = {val:.4f}")

    if os.path.exists(meta_path):
        with open(meta_path) as f:
            pca_meta = json.load(f)
        print(f"\nProjected PCA vectors:")
        for d in ALL_DIMS:
            vec = project_with_pca(raw, pca_meta, d)
            print(f"  {d}D: {[f'{v:.3f}' for v in vec[:4]]}{'...' if d>4 else ''}")
    else:
        print(f"\n[WARN] {meta_path} not found — run preprocess.py first to generate it.")