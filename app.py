from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys, os, random, tempfile, csv, json, time
import numpy as np

sys.path.append('./build')
import sqlmates_core
try:
    import rtree_core
    RTREE_AVAILABLE = True
    print("R-Tree module loaded ✓")
except ImportError:
    RTREE_AVAILABLE = False
    print("⚠ R-Tree module not found — R-Tree endpoints will return errors")

app = FastAPI(title="SQLMates KD-Tree + R-Tree API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────────────────────────────
ALL_DIMS  = [2, 5, 10, 20, 30]
AUDIO_DIR = "Data/genres_original"
IMAGE_DIR = "Data/images"

# ── Static file serving ─────────────────────────────────────────────────────────
if os.path.exists(AUDIO_DIR):
    app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
    print(f"Audio static: {AUDIO_DIR} → /audio")
else:
    print(f"[WARN] Audio dir not found: {AUDIO_DIR}")

if os.path.exists(IMAGE_DIR):
    app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")
    print(f"Image static: {IMAGE_DIR} → /images")
else:
    print(f"[WARN] Image dir not found: {IMAGE_DIR}")

# Engine caches
kd_engines: dict = {}
rt_engines: dict = {}

W = 72
def sep(t=''):
    if t: print(f"\n╔══ {t} {'═'*max(W-len(t)-4,0)}╗", flush=True)
    else: print('╚'+'═'*(W-1)+'╝\n', flush=True)
def log(m): print(f"  {m}", flush=True)

# ── Engine loaders ─────────────────────────────────────────────────────────────
def get_kd_engine(data_db, index_idx, dims, key):
    if key not in kd_engines:
        if not os.path.exists(data_db):
            raise HTTPException(404, f"KD index not found: {data_db}")
        log(f"Loading KD engine: {key} …")
        e = sqlmates_core.IndexEngine(data_db, index_idx, dims)
        if e.get_total_records() > 0:
            e.build_index()
        kd_engines[key] = e
        log(f"  ✓ {e.get_total_records():,} records × {dims}D")
    return kd_engines[key]

def get_rt_engine(data_db, tree_db, dims, key):
    if not RTREE_AVAILABLE:
        return None
    if key not in rt_engines:
        if not os.path.exists(data_db):
            return None
        log(f"Loading RT engine: {key} …")
        e = rtree_core.RTreeEngine(data_db, tree_db, dims)
        rt_engines[key] = e
        log(f"  ✓ RT {dims}D ready")
    return rt_engines[key]

# ── GTZAN row map ──────────────────────────────────────────────────────────────
GTZAN_ROWS = []
N_ORIGINAL = 0

def _load_gtzan_row_map():
    global GTZAN_ROWS, N_ORIGINAL
    # Try both case variants
    for csv_path in ["Data/features_3_sec.csv", "data/features_3_sec.csv"]:
        if os.path.exists(csv_path):
            break
    else:
        log("[WARN] features_3_sec.csv not found — audio links unavailable")
        return
    rows = []
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            fname = row.get("filename", "")
            genre = fname.split(".")[0] if fname else "unknown"
            rows.append({"genre": genre, "filename": fname})
    GTZAN_ROWS = rows
    N_ORIGINAL = len(rows)
    log(f"Loaded {N_ORIGINAL} GTZAN row mappings from {csv_path}")

def record_id_to_audio(record_id: int) -> dict:

    if not GTZAN_ROWS:
        return {"genre": None, "filename": None, "url": None, "record_id": record_id}

    orig_id = record_id % N_ORIGINAL
    info    = GTZAN_ROWS[orig_id]
    genre   = info["genre"]
    fname   = info["filename"]

    base   = fname[:-4] if fname.endswith(".wav") else fname
    parts  = base.split(".")
    if len(parts) == 3:
        real_fname = f"{parts[0]}.{parts[1]}.wav"
        try:
            seg     = int(parts[2])
            t_start = seg * 3
            t_end   = t_start + 3
            url = f"/audio/{genre}/{real_fname}#t={t_start},{t_end}"
        except ValueError:
            url = f"/audio/{genre}/{real_fname}"
    else:
        real_fname = fname
        url = f"/audio/{genre}/{fname}" if genre else None

    return {
        "genre":       genre,
        "filename":    fname,
        "real_file":   real_fname,
        "url":         url,
        "record_id":   record_id,
        "original_id": orig_id,
    }

IMAGE_META_BY_ID: dict = {}   # record_id (int) → {"label":..., "filepath":...}
IMAGE_META_LIST:  list = []   # fallback ordered list when record_id not in dict

def _load_image_metadata():
    global IMAGE_META_BY_ID, IMAGE_META_LIST
    for csv_path in ["Data/images_metadata.csv", "data/images_metadata.csv",
                     "Data/images/images_metadata.csv", "data/images/images_metadata.csv"]:
        if os.path.exists(csv_path):
            break
    else:
        log("[WARN] images_metadata.csv not found — image links unavailable")
        return

    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            IMAGE_META_LIST.append(row)
            # The CSV must have a record_id column; if missing we use list index
            rid_str = row.get("record_id", "").strip()
            if rid_str.isdigit():
                IMAGE_META_BY_ID[int(rid_str)] = row

    log(f"Loaded {len(IMAGE_META_LIST)} image metadata rows from {csv_path} "
        f"({len(IMAGE_META_BY_ID)} with explicit record_id)")

def record_id_to_image(record_id: int) -> dict:

    row = IMAGE_META_BY_ID.get(record_id)

    if row is None and IMAGE_META_LIST:
        idx = record_id % len(IMAGE_META_LIST)
        row = IMAGE_META_LIST[idx]

    if row is None:
        return {"label": None, "filepath": None, "url": None,
                "record_id": record_id, "original_id": record_id}

    label = row.get("label", "unknown")
    fpath = row.get("filepath", "").strip()

    url = None
    if fpath:
        # Normalise any backslashes (Windows paths in CSV)
        fpath = fpath.replace("\\", "/")
        try:
            # Make relative to IMAGE_DIR so the static mount resolves it
            rel = os.path.relpath(fpath, IMAGE_DIR).replace("\\", "/")
            if not rel.startswith(".."):
                url = "/images/" + rel
        except Exception:
            pass

    original_id = int(row.get("record_id", record_id)) if "record_id" in row else record_id

    return {
        "label":       label,
        "filepath":    fpath,
        "url":         url,
        "record_id":   record_id,
        "original_id": original_id,
    }

# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    os.makedirs("data", exist_ok=True)
    sep("STARTUP — SQLMates API")

    _load_gtzan_row_map()
    _load_image_metadata()

    # 2D random demo
    log("Initialising 2D random demo …")
    e = sqlmates_core.IndexEngine("data/data.db", "data/index.idx", 2)
    if e.get_total_records() == 0:
        log("  Generating 100,000 random 2D points …")
        rng = random.Random(42)
        for start in range(0, 100_000, 10_000):
            vecs = [[rng.uniform(0, 1000), rng.uniform(0, 1000)] for _ in range(10_000)]
            e.insert_vectors(vecs)
    e.build_index()
    kd_engines["random_2d"] = e
    log(f"  ✓ 2D engine ready ({e.get_total_records():,} records)")

    # Pre-load Audio KD engines
    for d in ALL_DIMS:
        db = f"data/kdtree_99k_{d}d_data.db"
        ix = f"data/kdtree_99k_{d}d_index.idx"
        if os.path.exists(db):
            try:   get_kd_engine(db, ix, d, f"audio_kd_{d}d")
            except Exception as ex: log(f"  [WARN] Audio KD {d}D: {ex}")

    # Pre-load Image KD engines
    for d in ALL_DIMS:
        db = f"data/img_kdtree_{d}d_data.db"
        ix = f"data/img_kdtree_{d}d_index.idx"
        if os.path.exists(db):
            try:   get_kd_engine(db, ix, d, f"img_kd_{d}d")
            except Exception as ex: log(f"  [WARN] IMG KD {d}D: {ex}")

    sep()

# ── 2D Canvas ──────────────────────────────────────────────────────────────────
class SearchQuery2D(BaseModel):
    x: float; y: float; k: int = 10

@app.post("/api/search")
def search_2d(query: SearchQuery2D):
    e = kd_engines.get("random_2d")
    if not e: raise HTTPException(500, "2D engine not loaded")
    r  = e.knn_search([query.x, query.y], query.k)
    sp = r['linear_time_us'] / r['kdtree_time_us'] if r['kdtree_time_us'] > 0 else 0
    sep("2D CANVAS QUERY")
    log(f"  Query: ({query.x:.1f}, {query.y:.1f})  k={query.k}")
    log(f"  KD-Tree: {r['kdtree_time_us']:,}µs  Linear: {r['linear_time_us']:,}µs  {sp:.2f}×")
    sep()
    return {
        "linear_time_us": r['linear_time_us'], "kdtree_time_us": r['kdtree_time_us'],
        "speedup": round(sp, 2), "coordinates": r['coordinates'],
        "num_results": len(r['record_ids']),
    }

# ── Audio helpers ──────────────────────────────────────────────────────────────
def _run_kd_audio(d: int, qv: list, k: int) -> dict:
    db = f"data/kdtree_99k_{d}d_data.db"
    ix = f"data/kdtree_99k_{d}d_index.idx"
    if not os.path.exists(db):
        return {"error": "index_not_built"}
    try:
        e  = get_kd_engine(db, ix, d, f"audio_kd_{d}d")
        r  = e.knn_search(qv, k)
        sp = r['linear_time_us'] / r['kdtree_time_us'] if r['kdtree_time_us'] > 0 else 0
        neighbors = [record_id_to_audio(rid) for rid in r['record_ids']]
        log(f"    KD {d}D: {r['kdtree_time_us']:,}µs  Lin={r['linear_time_us']:,}µs  {sp:.2f}×  ({len(neighbors)} neighbors)")
        for nb in neighbors:
            log(f"      KD #{nb['record_id']:>6}  [{nb['genre']}]  {nb['filename']}")
        return {
            "dims": d, "kdtree_time_us": r['kdtree_time_us'],
            "linear_time_us": r['linear_time_us'], "speedup": round(sp, 2),
            "record_ids": r['record_ids'], "neighbors": neighbors,
            "n_records": e.get_total_records(),
        }
    except Exception as ex:
        log(f"    KD {d}D error: {ex}")
        return {"error": str(ex)}

def _run_rt_audio(d: int, qv: list, k: int) -> dict:
    if not RTREE_AVAILABLE:
        return {"error": "rtree_not_available"}
    rdb = f"data/rtree_99k_{d}d_data.db"
    rtb = f"data/rtree_99k_{d}d_tree.db"
    if not os.path.exists(rdb):
        return {"error": "index_not_built"}
    try:
        e = get_rt_engine(rdb, rtb, d, f"audio_rt_{d}d")
        if not e:
            return {"error": "engine_load_failed"}
        r  = e.knn_search(qv, k)
        sp = r['linear_time_us'] / r['rtree_time_us'] if r['rtree_time_us'] > 0 else 0
        neighbors = [record_id_to_audio(rid) for rid in r['record_ids']]
        log(f"    RT {d}D: {r['rtree_time_us']:,}µs  Lin={r['linear_time_us']:,}µs  {sp:.2f}×  ({len(neighbors)} neighbors)")
        for nb in neighbors:
            log(f"      RT #{nb['record_id']:>6}  [{nb['genre']}]  {nb['filename']}")
        return {
            "dims": d, "rtree_time_us": r['rtree_time_us'],
            "linear_time_us": r['linear_time_us'], "speedup": round(sp, 2),
            "record_ids": r['record_ids'], "neighbors": neighbors,
            "n_records": e.get_total_records(),
        }
    except Exception as ex:
        log(f"    RT {d}D error: {ex}")
        return {"error": str(ex)}

# ── Audio search endpoint ──────────────────────────────────────────────────────
@app.post("/api/search_audio")
async def search_audio(file: UploadFile = File(...), k: int = 5):
    meta_path = "data/pca_meta.json"
    if not os.path.exists(meta_path):
        raise HTTPException(404, "Audio PCA metadata not found. Run: python scripts/preprocess.py")

    suffix = os.path.splitext(file.filename or ".mp3")[1] or ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        sys.path.insert(0, './scripts')
        from extract_audio_features import extract_for_all_dims

        sep(f"AUDIO SEARCH — {file.filename}  k={k}")
        t0 = time.time()
        with open(meta_path) as f:
            pca_meta = json.load(f)

        feats_by_dim = extract_for_all_dims(tmp_path, pca_meta, ALL_DIMS)
        log(f"Feature extraction + PCA: {time.time()-t0:.2f}s")

        kd_results, rt_results = {}, {}
        for d in ALL_DIMS:
            log(f"\n── {d}D ──────────────────────────────")
            qv = feats_by_dim[d]
            kd_results[d] = _run_kd_audio(d, qv, k)
            rt_results[d] = _run_rt_audio(d, qv, k)

        sep("AUDIO SUMMARY")
        log(f"  {'Dim':<5} {'KD-Tree':>12} {'R-Tree':>12} {'Linear':>12} {'KD×':>7} {'RT×':>7}")
        for d in ALL_DIMS:
            kd = kd_results[d]; rt = rt_results[d]
            kdT  = f"{kd['kdtree_time_us']:,}µs"  if 'kdtree_time_us' in kd else kd.get('error','—')[:10]
            rtT  = f"{rt['rtree_time_us']:,}µs"   if 'rtree_time_us'  in rt else rt.get('error','—')[:10]
            lin  = kd.get('linear_time_us') or rt.get('linear_time_us')
            linS = f"{lin:,}µs" if lin else "—"
            log(f"  {str(d)+'D':<5} {kdT:>12} {rtT:>12} {linS:>12} {str(kd.get('speedup','—'))+'×':>7} {str(rt.get('speedup','—'))+'×':>7}")
        sep()

        return {
            "filename":   file.filename,
            "kd_results": {str(d): kd_results[d] for d in ALL_DIMS},
            "rt_results": {str(d): rt_results[d] for d in ALL_DIMS},
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ── Image helpers ──────────────────────────────────────────────────────────────
def _run_kd_image(d: int, qv: list, k: int) -> dict:
    db = f"data/img_kdtree_{d}d_data.db"
    ix = f"data/img_kdtree_{d}d_index.idx"
    if not os.path.exists(db):
        return {"error": "index_not_built"}
    try:
        e  = get_kd_engine(db, ix, d, f"img_kd_{d}d")
        r  = e.knn_search(qv, k)
        sp = r['linear_time_us'] / r['kdtree_time_us'] if r['kdtree_time_us'] > 0 else 0
        neighbors = [record_id_to_image(rid) for rid in r['record_ids']]
        log(f"    KD {d}D: {r['kdtree_time_us']:,}µs  Lin={r['linear_time_us']:,}µs  {sp:.2f}×  ({len(neighbors)} images)")
        for nb in neighbors:
            log(f"      KD #{nb['record_id']:>6}  [{nb['label']}]  {nb['filepath']}")
        return {
            "dims": d, "kdtree_time_us": r['kdtree_time_us'],
            "linear_time_us": r['linear_time_us'], "speedup": round(sp, 2),
            "record_ids": r['record_ids'], "neighbors": neighbors,
            "n_records": e.get_total_records(),
        }
    except Exception as ex:
        log(f"    KD {d}D error: {ex}")
        return {"error": str(ex)}

def _run_rt_image(d: int, qv: list, k: int) -> dict:
    if not RTREE_AVAILABLE:
        return {"error": "rtree_not_available"}
    rdb = f"data/img_rtree_{d}d_data.db"
    rtb = f"data/img_rtree_{d}d_tree.db"
    if not os.path.exists(rdb):
        return {"error": "index_not_built"}
    try:
        e = get_rt_engine(rdb, rtb, d, f"img_rt_{d}d")
        if not e:
            return {"error": "engine_load_failed"}
        r  = e.knn_search(qv, k)
        sp = r['linear_time_us'] / r['rtree_time_us'] if r['rtree_time_us'] > 0 else 0
        neighbors = [record_id_to_image(rid) for rid in r['record_ids']]
        log(f"    RT {d}D: {r['rtree_time_us']:,}µs  Lin={r['linear_time_us']:,}µs  {sp:.2f}×  ({len(neighbors)} images)")
        for nb in neighbors:
            log(f"      RT #{nb['record_id']:>6}  [{nb['label']}]  {nb['filepath']}")
        return {
            "dims": d, "rtree_time_us": r['rtree_time_us'],
            "linear_time_us": r['linear_time_us'], "speedup": round(sp, 2),
            "record_ids": r['record_ids'], "neighbors": neighbors,
            "n_records": e.get_total_records(),
        }
    except Exception as ex:
        log(f"    RT {d}D error: {ex}")
        return {"error": str(ex)}

# ── Image search endpoint ──────────────────────────────────────────────────────
@app.post("/api/search_image")
async def search_image(file: UploadFile = File(...), k: int = 5):
    meta_path = "data/pca_images_meta.json"
    if not os.path.exists(meta_path):
        raise HTTPException(404, "Image PCA metadata not found. Run: python scripts/preprocess_images.py")

    suffix = os.path.splitext(file.filename or ".jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        sys.path.insert(0, './scripts')
        from extract_image_features import extract_for_all_dims

        sep(f"IMAGE SEARCH — {file.filename}  k={k}")
        t0 = time.time()
        with open(meta_path) as f:
            pca_meta = json.load(f)
        feats_by_dim = extract_for_all_dims(tmp_path, pca_meta, ALL_DIMS)
        log(f"CNN + PCA extraction: {time.time()-t0:.2f}s")

        kd_results, rt_results = {}, {}
        for d in ALL_DIMS:
            log(f"\n── {d}D ──────────────────────────────")
            qv = feats_by_dim[d]
            kd_results[d] = _run_kd_image(d, qv, k)
            rt_results[d] = _run_rt_image(d, qv, k)

        sep("IMAGE SUMMARY")
        for d in ALL_DIMS:
            kd = kd_results[d]; rt = rt_results[d]
            kdT = f"{kd['kdtree_time_us']:,}µs" if 'kdtree_time_us' in kd else kd.get('error','—')[:12]
            rtT = f"{rt['rtree_time_us']:,}µs"  if 'rtree_time_us'  in rt else rt.get('error','—')[:12]
            log(f"  {str(d)+'D':<5} KD={kdT}  RT={rtT}  KD×={kd.get('speedup','—')}  RT×={rt.get('speedup','—')}")
        sep()

        return {
            "filename":   file.filename,
            "kd_results": {str(d): kd_results[d] for d in ALL_DIMS},
            "rt_results": {str(d): rt_results[d] for d in ALL_DIMS},
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ── Utility ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status":          "ok",
        "kd_engines":      list(kd_engines.keys()),
        "rt_engines":      list(rt_engines.keys()),
        "rtree_available": RTREE_AVAILABLE,
        "image_meta_rows": len(IMAGE_META_LIST),
        "image_meta_by_id": len(IMAGE_META_BY_ID),
        "gtzan_rows":      N_ORIGINAL,
    }