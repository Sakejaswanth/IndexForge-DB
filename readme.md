# IndexForge-DB: Multidimensional Search Engine (KD-Tree & R-Tree)

**IIT Kharagpur · CS39202 Database Management Systems · 2025–26**

This project implements, benchmarks, and demonstrates two disk-resident multidimensional index structures — **KD-Tree** and **R-Tree** — built entirely from scratch in C++. The central engineering focus is the **page-based storage engine** with an **LRU Buffer Pool Manager**, which mirrors how real database systems (PostgreSQL, InnoDB) manage disk I/O. A brute-force linear scan serves as the correctness baseline and performance reference. Experiments vary dimensionality, dataset size, and query selectivity to reveal exactly when and why tree-based indexing breaks down under the curse of dimensionality.

---

## Build prerequisites

- Python 3.10+ with `numpy`, `fastapi`, `uvicorn`, and `pybind11`
- CMake 3.15+ and a C++17 compiler
- Node.js 18+ for the React dashboard

On Windows, configure the native modules with Visual Studio or another MSVC-compatible C++ toolchain. From the repository root:

```powershell
cmake -S src -B build
cmake --build build --config Release
Push-Location frontend
npm install
npm run build
Pop-Location
```

Generated datasets and native build outputs are intentionally excluded by `.gitignore`.

## Core Contributions

- **Disk-resident KD-Tree** with branch-and-bound kNN pruning, built on top of a custom paged storage engine
- **Disk-resident R-Tree** with quadratic split strategy and MINDIST-based kNN traversal
- **Page-based storage engine** — `DiskManager` handles raw page I/O; `BufferPoolManager` caches hot pages using LRU eviction; `DataFile` stores fixed-size float vectors across pages
- **LRU Replacer** — O(1) eviction using a doubly-linked list + hash map (frame\_id → iterator)
- **pybind11 bindings** exposing the C++ engine to a FastAPI backend and a React benchmark dashboard
- **Benchmarking suite** measuring query latency, build time, and cache hit rate across five dimensionalities (2D, 5D, 10D, 20D, 30D) on two real datasets

---

## Project Structure

```
IndexForge-DB/
├── src/
│   ├── page.h                      # Page struct: 4096-byte aligned buffer
│   ├── disk_manager.cpp/h          # Raw page read/write via fstream
│   ├── lru_replacer.cpp/h          # LRU policy: O(1) evict + record-access
│   ├── buffer_pool_manager.cpp/h   # Buffer pool: fetch, new, unpin, mark-dirty, flush
│   ├── data_file.cpp/h             # Vector storage: header page + data pages
│   ├── kdtree_disk.cpp/h           # KD-Tree: build + kNN via branch-and-bound
│   ├── rtree_node.h                # MBR struct + RTreeNode serialization
│   ├── rtree_file.cpp/h            # R-Tree page I/O layer
│   ├── rtree.cpp/h                 # R-Tree: insert, quadratic split, kNN
│   ├── search_engine.cpp/h         # Linear scan baseline + timing template
│   ├── bind_kdtree.cpp             # pybind11 → sqlmates_core (KD-Tree)
│   ├── bind_rtree.cpp              # pybind11 → rtree_core (R-Tree)
│   └── main.cpp                    # Standalone C++ benchmark (no Python)
├── scripts/
│   ├── load_dataset.py             # Builds audio indexes at all dims
│   ├── preprocess_images.py        # CNN feature extraction + image indexes
│   ├── extract_audio_features.py   # librosa 30-feature extractor
│   └── extract_image_features.py   # MobileNetV2 + PCA projection
├── frontend/src/
│   ├── App.jsx                     # React benchmark dashboard
│   └── main.jsx
├── Data/                           # Raw datasets (not committed)
├── data/                           # Generated .db/.idx files (not committed)
├── app.py                          # FastAPI backend
└── CMakeLists.txt
```

---

## Storage Engine Design

This is the central engineering contribution of the project. Every page read and write — whether for a KD-Tree node, an R-Tree node, or a raw data record — goes through the same layered stack.

```
KDTreeDisk / RTree / DataFile
          │
          ▼
  BufferPoolManager          ← LRU cache (N frames of 4096 bytes each)
          │
          ▼
     DiskManager             ← fstream-based page I/O
          │
          ▼
     .db file on disk        ← page 0: header, page 1+: data/index
```

### Page Layout

Every file is divided into fixed-size 4096-byte pages. The `Page` struct is just a header int (`page_id`) and a raw `char data_[4096]` buffer. Higher layers serialize their structures into this buffer directly using `memcpy`.

### DiskManager

Wraps a single `std::fstream`. Provides `AllocatePage()`, `ReadPage(page_id, buf)`, and `WritePage(page_id, buf)`. Computes byte offsets as `page_id × PAGE_SIZE`. On construction it counts existing pages from file size so the state survives restarts.

### LRU Replacer

Manages which buffer frames are evictable. Internally uses:

- `std::list<int>` — doubly-linked list of frame IDs, front = MRU, back = LRU
- `std::unordered_map<int, std::list<int>::iterator>` — O(1) lookup into the list

**Key operations:**

| Operation | Complexity | What it does |
|-----------|-----------|--------------|
| `RecordAccess(frame)` | O(1) | Move frame to MRU front (or insert) |
| `Evict(frame*)` | O(1) | Remove and return LRU back element |
| `Remove(frame)` | O(1) | Remove a frame when it gets pinned |

When a frame's pin count reaches 0, it's returned to the replacer via `RecordAccess`. When it's actively being used (pin count > 0), it's removed from the replacer so it can't be evicted.

### BufferPoolManager

Maintains a fixed pool of `pool_size` frames. Each frame has a `FrameMetadata` struct:

```cpp
struct FrameMetadata {
    int  page_id   = -1;
    int  pin_count = 0;
    bool is_dirty  = false;
};
```

**`FetchPage(page_id)`** — checks the `page_table_` hash map for a cache hit. On a miss, calls `GetVictimFrame()`, flushes the evicted frame if dirty, reads the new page from disk, and registers the mapping.

**`NewPage()`** — calls `DiskManager::AllocatePage()` to get a new `page_id`, zeroes the frame, and registers it with pin count 1.

**`UnpinPage(page_id)`** — decrements pin count. When it reaches 0, the frame is handed to `LRUReplacer::RecordAccess()`.

**`MarkDirty(page_id)`** — sets `is_dirty = true` so the frame is written back on eviction.

**`FlushAllPages()`** — writes all dirty frames to disk. Called on shutdown and after index builds.

### DataFile

Stores a flat array of fixed-size float vectors (`dims × sizeof(float)` bytes each). Layout:

```
Page 0:  [ total_records (4B) | total_data_pages (4B) ]
Page 1+: [ page_record_count (4B) | vec_0 | vec_1 | ... ]
```

`records_per_page = (PAGE_SIZE - 4) / record_size`. For 2D vectors (8 bytes each), this is ~510 records per page. `AppendRecord` and `ReadRecord` compute `page_id = record_id / records_per_page + 1` and use the BPM.

### Cache Statistics

`BufferPoolManager` exposes `GetHitCount()` and `GetMissCount()`. These are returned by the Python binding after every kNN search so the dashboard can display cache hit rates alongside query latency.

---

## KD-Tree Implementation

### Structure

Each node is a fixed-size 16-byte struct:

```cpp
struct KDNode {
    int record_id;      // index into DataFile
    int left_node_id;   // -1 = null
    int right_node_id;  // -1 = null
    int axis;           // split dimension
};
```

Nodes are packed into pages via the BPM. `nodes_per_page = PAGE_SIZE / sizeof(KDNode)` = 256.

### Build

`BuildIndex()` recursively partitions `record_ids` using `std::nth_element` (O(N) median selection) cycling through `depth % dims`. Nodes are assigned IDs in pre-order and written via `WriteNode`. After the full build, `FlushAllPages()` persists the index.

### kNN Search — Branch and Bound

`KNNSearchRecursive` maintains a **max-heap** of size k (worst-distance at the top). At each node:

1. Read the node and its data vector (two BPM page fetches)
2. Compute Euclidean distance; update the heap
3. Descend into the more-likely subtree first
4. **Pruning check:** only backtrack into the other subtree if `axis_dist < heap.top().first` — i.e. the splitting plane is closer than the current k-th best

At low dimensions this prunes the vast majority of the tree. At high dimensions every `axis_dist` is smaller than the heap top (because all distances are large), so pruning almost never fires and the tree degrades toward linear scan.

---

## R-Tree Implementation

### Structure

Each node stores up to `MaxEntries(dim)` entries. Each entry is:

```
[ MBR: 2×dim×4 bytes | child_or_record: 4 bytes ]
```

`MaxEntries(dim) = (PAGE_SIZE - 8) / (2×dim×4 + 4)`. For dim=2 this is ~136; for dim=30 it drops to ~15. Min fill is 40% of max.

### Insert + Quadratic Split

`Insert` calls `ChooseLeaf` (minimum MBR expansion heuristic), appends the new entry, and splits on overflow using `QuadraticSplit`: seeds are the pair with maximum dead space in their combined MBR; remaining entries are distributed by expansion cost difference. Split propagates up via `AdjustTree`, possibly creating a new root.

### kNN Search — MINDIST Priority Queue

Uses a min-heap ordered by `MBR::MinDistSq(query_point)`. The root MBR is pushed first. The loop always pops the closest entry:

- If it's a leaf entry → record found, add to results
- If it's an internal node → push all children with their MINDIST

This is the **branch-and-bound** equivalent for R-Trees: subtrees whose MBR is farther than the current k-th best are naturally never popped from the heap before the search completes.

---

## Benchmark Results

All experiments run on a single CPU core. Dataset sizes: 99K records (audio), 12K records (images), 100K records (2D random).

### 2D Random Points (100K records)

| Method | Time (µs) | Speedup |
|--------|-----------|---------|
| KD-Tree | ~700 | **300×** |
| R-Tree | ~600 | **350×** |
| Linear | ~210,000 | 1× |

### GTZAN Audio (99K records, 30 features)

| Dim | KD-Tree | R-Tree | Linear | KD× | RT× |
|-----|---------|--------|--------|-----|-----|
| 2D | 210 µs | 161 µs | 17,297 µs | **82×** | **100×** |
| 5D | 420 µs | 2,121 µs | 14,572 µs | **34×** | 7× |
| 10D | 1,897 µs | 20,359 µs | 18,134 µs | **9.6×** | 0.87× |
| 20D | 26,603 µs | 45,917 µs | 22,419 µs | 0.84× | 1.5× |
| 30D | 25,600 µs | 65,155 µs | 26,713 µs | 1.04× | 0.35× |

### Stanford Dogs Images (12K records, CNN→PCA features)

| Dim | KD-Tree | R-Tree | Linear | KD× | RT× |
|-----|---------|--------|--------|-----|-----|
| 2D | 94 µs | 69 µs | 1,331 µs | **14×** | **20×** |
| 5D | 439 µs | 188 µs | 1,277 µs | **2.9×** | **7.6×** |
| 10D | 783 µs | 304 µs | 1,261 µs | **1.6×** | **5.7×** |
| 20D | 2,240 µs | 706 µs | 1,900 µs | 0.85× | **2.9×** |
| 30D | 4,805 µs | — | 2,158 µs | 0.45× | — |

### Observations

- **R-Tree beats KD-Tree at moderate dimensions (5D–20D)** on the image dataset. MBRs prune more effectively than axis-aligned hyperplanes when data is clustered.
- **KD-Tree beats R-Tree at very low dimensions (2D)** due to lower per-node overhead.
- **Both degrade beyond 20D** — the curse of dimensionality. At 30D KD-Tree is slower than linear scan because the branch-and-bound pruning condition fires on nearly every node, adding disk I/O overhead on top of full traversal.
- **LRU cache hit rates exceed 85%** on warm queries, which is why the second query on any dataset is substantially faster than the first.
- **R-Tree 30D** is skipped in image preprocessing — at that dimensionality MBR overlap becomes near-universal, causing the R-Tree to visit more pages than a full scan with worse constants.

---

## Cloning and Running

### Clone

```powershell
git clone https://github.com/Sakejaswanth/IndexForge-DB.git
cd IndexForge-DB
```

### Step 1 — Python dependencies

```powershell
pip install -r requirements.txt
```

*(Includes `fastapi`, `uvicorn`, `python-multipart`, `pybind11`, `librosa`, `numpy`, `pandas`, `scikit-learn`, `torch`, `torchvision`, `pillow`).*

### Step 2 — Build C++ modules (Optional)

If a C++17 compiler (MSVC, GCC, or Clang) is available:

```powershell
cmake -S src -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

> **Note**: If C++ modules are not built, IndexForge automatically falls back to an optimized pure-Python storage engine (`python_core.py`), ensuring the entire app runs out-of-the-box on any OS or cloud host!

### Step 3 — Download datasets (or use auto-generated sample demo data)

To use full datasets:
```bash
pip install kaggle
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json

kaggle datasets download -d andradaolteanu/gtzan-dataset-music-genre-classification
kaggle datasets download -d jessicali9530/stanford-dogs-dataset

unzip gtzan-dataset-music-genre-classification.zip -d Data/
unzip stanford-dogs-dataset.zip -d Data/
```

*(If Kaggle datasets are not downloaded, sample demo data is automatically seeded on first launch, or via `python scripts/generate_sample_data.py`).*

### Step 4 — Build indexes

```powershell
New-Item -ItemType Directory -Force data

# Audio: GTZAN 99K records at 5 dimensionalities (or sample data)
python scripts/load_dataset.py --dataset gtzan_99k

# Images: Stanford Dogs 12K records at 5 dimensionalities
python scripts/preprocess_images.py
```

### Step 5 — Run standalone C++ benchmark

```powershell
./build/Release/benchmark.exe
```

Outputs KD-Tree vs linear timing for 100K random 2D points directly from C++.

### Step 6 — Run the full application (Single-Command Hosting)

Build the frontend once:
```powershell
cd frontend
npm install
npm run build
cd ..
```

Then start the unified server:
```powershell
python app.py
```
Open **http://localhost:8004** to access the full interactive dashboard and all API endpoints!

### Docker Deployment

To build and run anywhere with containerization:
```powershell
docker build -t indexforge-db .
docker run -p 8004:8004 indexforge-db
```

---

## Key Design Decisions

**Why page-based storage instead of in-memory trees?**
Real database index structures are disk-resident. Storing nodes in fixed-size pages and going through the buffer pool makes the I/O pattern measurable and the cache behaviour explicit. The LRU hit rate is reported per query alongside latency.

**Why pybind11 instead of a pure Python implementation?**
The inner loops of kNN search (reading thousands of nodes, computing distances) are compute-bound. A pure Python implementation would be 100–1000× slower and would make the linear scan competitive even at 2D, eliminating the experiment's signal.

**Why quadratic split for R-Tree?**
Linear split is faster to compute but produces lower-quality splits (larger MBRs, more overlap). Quadratic split was chosen to maximise pruning effectiveness — the goal is to demonstrate the best case for R-Tree before it degrades at high dimensions.

**Why PCA for image features?**
MobileNetV2 produces 1280-dimensional embeddings. Running KD-Tree or R-Tree at 1280D would be meaningless — the curse of dimensionality would dominate immediately. PCA reduces to the same five dimensionalities used for audio, making the comparison fair.

---

## References

- Bentley, J. L. (1975). *Multidimensional binary search trees used for associative searching.* CACM 18(9).
- Guttman, A. (1984). *R-trees: A dynamic index structure for spatial searching.* SIGMOD.
- Roussopoulos, N., Kelley, S., & Vincent, F. (1995). *Nearest neighbor queries.* SIGMOD.
- Beyer, K. et al. (1999). *When is nearest neighbor meaningful?* ICDT. (Curse of dimensionality)
- Sandler, M. et al. (2018). *MobileNetV2: Inverted residuals and linear bottlenecks.* CVPR.
