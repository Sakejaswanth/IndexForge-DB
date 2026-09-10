#include "disk_manager.h"
#include "buffer_pool_manager.h"
#include "data_file.h"
#include "kdtree_disk.h"
#include "search_engine.h"
#include <iostream>
#include <random>

// ── Buffer pool sizes ─────────────────────────────────────────────────────────
// Tune these based on available RAM.
// For a 100K-point 2D dataset:
//   data pages ≈  100K / ~500 records/page  ≈ 200 pages  →  64 frames is plenty
//   index pages ≈ 100K nodes / ~341 nodes/page ≈ 293 pages → 128 frames is fine
constexpr int DATA_POOL_SIZE  =  64;
constexpr int INDEX_POOL_SIZE = 128;

int main() {
    std::cout << "--- SQLMates KD-Tree Benchmark (LRU Buffer Pool) ---\n";

    // 1. Setup storage layer
    DiskManager data_dm("data.db");
    DiskManager index_dm("kdtree.idx");

    // 2. Wrap in LRU buffer pools
    BufferPoolManager data_bpm (DATA_POOL_SIZE,  &data_dm);
    BufferPoolManager index_bpm(INDEX_POOL_SIZE, &index_dm);

    // 3. Build higher-level structures on top of the pools
    DataFile   data_file(&data_bpm, 2);          // 2D points
    KDTreeDisk kdtree   (&index_bpm, &data_file, 2);

    const int num_points = 100000;
    const int k          = 10;

    // 4. Insert data only if the file is fresh
    if (data_file.GetTotalRecords() == 0) {
        std::cout << "Generating " << num_points << " random 2D points...\n";
        std::mt19937 gen(42);
        std::uniform_real_distribution<float> dist(0.0f, 1000.0f);

        for (int i = 0; i < num_points; i++)
            data_file.AppendRecord({dist(gen), dist(gen)});

        std::cout << "Data insertion complete.\n";
        std::cout << "Building Disk-Resident KD-Tree...\n";
        kdtree.BuildIndex();
        std::cout << "Index build complete.\n";
    } else {
        std::cout << "Found existing database with "
                  << data_file.GetTotalRecords() << " records.\n";
        kdtree.BuildIndex();   // rebuild to populate root_node_id_ in memory
    }

    // 5. Benchmark
    std::vector<float> query = {500.0f, 500.0f};
    std::cout << "\nQuerying Top " << k
              << " neighbors for point (" << query[0] << ", " << query[1] << ")...\n";

    // Reset stats so we measure only the query phase
    data_bpm.ResetStats();
    index_bpm.ResetStats();

    std::vector<int> linear_results;
    long long linear_time = SearchEngine::MeasureTimeMicroseconds([&]() {
        linear_results = SearchEngine::LinearSearchKNN(&data_file, query, k);
    });

    std::vector<int> tree_results;
    long long tree_time = SearchEngine::MeasureTimeMicroseconds([&]() {
        tree_results = kdtree.KNNSearch(query, k);
    });

    // 6. Results
    std::cout << "-----------------------------------\n";
    std::cout << "Linear Search Time  : " << linear_time << " µs\n";
    std::cout << "KD-Tree Time        : " << tree_time   << " µs\n";
    float speedup = (float)linear_time / (float)tree_time;
    std::cout << "Speedup             : " << speedup     << "x faster!\n";
    std::cout << "-----------------------------------\n";
    std::cout << "Data  BPM — hits: "  << data_bpm.GetHitCount()
              << "  misses: " << data_bpm.GetMissCount()  << "\n";
    std::cout << "Index BPM — hits: "  << index_bpm.GetHitCount()
              << "  misses: " << index_bpm.GetMissCount() << "\n";

    return 0;
}