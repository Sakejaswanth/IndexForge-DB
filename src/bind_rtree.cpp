#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "disk_manager.h"
#include "buffer_pool_manager.h"
#include "data_file.h"
#include "rtree.h"
#include <memory>
#include <chrono>
#include <queue>    
#include <cmath>
#include <vector>
#include <algorithm>

namespace py = pybind11;

constexpr int DATA_POOL_SIZE = 128;
constexpr int TREE_POOL_SIZE = 256;

class RTreeEngine {
private:
    std::unique_ptr<DiskManager>       data_dm_;
    std::unique_ptr<BufferPoolManager> data_bpm_;
    std::unique_ptr<DataFile>          data_file_;

    std::unique_ptr<DiskManager>       tree_dm_;
    std::unique_ptr<BufferPoolManager> tree_bpm_;
    std::unique_ptr<RTree>             rtree_;

    int dims_;

public:
    RTreeEngine(const std::string& data_path,
                const std::string& tree_path,
                int dims)
        : dims_(dims)
    {
        data_dm_   = std::make_unique<DiskManager>(data_path);
        tree_dm_   = std::make_unique<DiskManager>(tree_path);

        data_bpm_  = std::make_unique<BufferPoolManager>(data_dm_.get(), DATA_POOL_SIZE);
        tree_bpm_  = std::make_unique<BufferPoolManager>(tree_dm_.get(), TREE_POOL_SIZE);

        data_file_ = std::make_unique<DataFile>(data_dm_.get(), data_bpm_.get(), dims);

        rtree_ = std::make_unique<RTree>(
            tree_dm_.get(), tree_bpm_.get(), data_file_.get(), dims);
    }

    void insert_vectors(const std::vector<std::vector<float>>& vecs) {
        for (const auto& v : vecs)
            rtree_->Insert(v);
    }

    int get_total_records() const {
        return data_file_->GetTotalRecords();
    }

    int get_tree_height() const {
        return rtree_->GetTreeHeight();
    }

    // Linear KNN over DataFile (baseline)
    std::vector<std::pair<int, float>> linear_knn(
        const std::vector<float>& query, int k) const
    {
        int n = data_file_->GetTotalRecords();

        // max-heap: (dist_sq, record_id)
        using P = std::pair<float, int>;
        std::priority_queue<P> pq;

        for (int i = 0; i < n; ++i) {
            auto vec = data_file_->ReadRecord(i);
            float d = 0.0f;
            for (int j = 0; j < dims_; ++j)
                d += (vec[j] - query[j]) * (vec[j] - query[j]);
            pq.push(std::make_pair(d, i));
            if ((int)pq.size() > k) pq.pop();
        }

        std::vector<std::pair<int, float>> result;
        while (!pq.empty()) {
            result.push_back(std::make_pair(pq.top().second,
                                            std::sqrt(pq.top().first)));
            pq.pop();
        }
        std::reverse(result.begin(), result.end());
        return result;
    }

    py::dict knn_search(const std::vector<float>& query, int k) {
        // Linear scan baseline
        long long linear_us;
        std::vector<std::pair<int, float>> linear_results;
        {
            auto t0 = std::chrono::high_resolution_clock::now();
            linear_results = linear_knn(query, k);
            auto t1 = std::chrono::high_resolution_clock::now();
            linear_us = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
        }

        // R-Tree KNN
        tree_dm_->ResetReadCount();
        long long rtree_us;
        std::vector<std::pair<int, float>> rtree_results;
        {
            auto t0 = std::chrono::high_resolution_clock::now();
            rtree_results = rtree_->KNNSearch(query, k);
            auto t1 = std::chrono::high_resolution_clock::now();
            rtree_us = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
        }
        int pages_read = tree_dm_->GetReadCount();

        // Extract record IDs from R-Tree results
        std::vector<int> record_ids;
        for (auto& p : rtree_results)
            record_ids.push_back(p.first);

        // Fetch actual vectors for the top-k results
        std::vector<std::vector<float>> coordinates;
        for (int id : record_ids)
            coordinates.push_back(data_file_->ReadRecord(id));

        py::dict response;
        response["linear_time_us"] = linear_us;
        response["rtree_time_us"]  = rtree_us;
        response["record_ids"]     = record_ids;
        response["coordinates"]    = coordinates;
        response["pages_read"]     = pages_read;
        response["tree_height"]    = rtree_->GetTreeHeight();
        return response;
    }
};

PYBIND11_MODULE(rtree_core, m) {
    py::class_<RTreeEngine>(m, "RTreeEngine")
        .def(py::init<const std::string&, const std::string&, int>())
        .def("insert_vectors",    &RTreeEngine::insert_vectors)
        .def("get_total_records", &RTreeEngine::get_total_records)
        .def("get_tree_height",   &RTreeEngine::get_tree_height)
        .def("knn_search",        &RTreeEngine::knn_search);
}