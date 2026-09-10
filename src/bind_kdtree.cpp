#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "disk_manager.h"
#include "buffer_pool_manager.h"
#include "data_file.h"
#include "kdtree_disk.h"
#include "search_engine.h"
#include <memory>
#include <chrono>
#include <queue>

namespace py = pybind11;

constexpr int DATA_POOL_SIZE  =  128;
constexpr int INDEX_POOL_SIZE =  256;

class IndexEngine {
private:
    std::unique_ptr<DiskManager>       data_dm_;
    std::unique_ptr<BufferPoolManager> data_bpm_;
    std::unique_ptr<DataFile>          data_file_;

    std::unique_ptr<DiskManager>       index_dm_;
    std::unique_ptr<BufferPoolManager> index_bpm_;
    std::unique_ptr<KDTreeDisk>        kdtree_;

    int dims_;

public:
    IndexEngine(const std::string& data_path,
                const std::string& index_path,
                int dims)
        : dims_(dims)
    {
        data_dm_   = std::make_unique<DiskManager>(data_path);
        index_dm_  = std::make_unique<DiskManager>(index_path);

        data_bpm_  = std::make_unique<BufferPoolManager>(data_dm_.get(),  DATA_POOL_SIZE);
        index_bpm_ = std::make_unique<BufferPoolManager>(index_dm_.get(), INDEX_POOL_SIZE);

        data_file_ = std::make_unique<DataFile>(data_dm_.get(), data_bpm_.get(), dims);

        kdtree_ = std::make_unique<KDTreeDisk>(
            index_dm_.get(), index_bpm_.get(), data_file_.get(), dims);
    }

    void insert_vectors(const std::vector<std::vector<float>>& vecs) {
        for (const auto& v : vecs)
            data_file_->AppendRecord(v);
    }

    void build_index() {
        kdtree_->BuildIndex();
    }

    int get_total_records() {
        return data_file_->GetTotalRecords();
    }

    py::dict knn_search(std::vector<float> query, int k) {
        // Linear scan baseline
        std::vector<int> linear_results;
        long long linear_time = SearchEngine::MeasureTimeMicroseconds([&]() {
            linear_results = SearchEngine::LinearSearchKNN(data_file_.get(), query, k);
        });

        // KD-Tree search
        std::vector<int> tree_results;
        long long tree_time = SearchEngine::MeasureTimeMicroseconds([&]() {
            tree_results = kdtree_->KNNSearch(query, k);
        });

        // Fetch coordinates for the tree results
        std::vector<std::vector<float>> result_coords;
        for (int id : tree_results)
            result_coords.push_back(data_file_->ReadRecord(id));

        py::dict response;
        response["linear_time_us"] = linear_time;
        response["kdtree_time_us"] = tree_time;
        response["record_ids"]     = tree_results;
        response["coordinates"]    = result_coords;
        return response;
    }
};

PYBIND11_MODULE(sqlmates_core, m) {
    py::class_<IndexEngine>(m, "IndexEngine")
        .def(py::init<const std::string&, const std::string&, int>())
        .def("insert_vectors",    &IndexEngine::insert_vectors)
        .def("build_index",       &IndexEngine::build_index)
        .def("get_total_records", &IndexEngine::get_total_records)
        .def("knn_search",        &IndexEngine::knn_search);
}