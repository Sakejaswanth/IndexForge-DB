#include "kdtree_disk.h"
#include <algorithm>
#include <cstring>
#include <numeric>
#include <stdexcept>

KDTreeDisk::KDTreeDisk(DiskManager* index_dm, BufferPoolManager* index_bpm,
                       DataFile* data_file, int dims) {
    index_dm_       = index_dm;
    index_bpm_      = index_bpm;
    data_file_      = data_file;
    dims_           = dims;
    nodes_per_page_ = PAGE_SIZE / sizeof(KDNode);
    total_nodes_    = 0;
    root_node_id_   = -1;
}

void KDTreeDisk::WriteNode(int node_id, const KDNode& node) {
    int page_id = node_id / nodes_per_page_;
    int offset  = (node_id % nodes_per_page_) * sizeof(KDNode);

    // Allocate pages up to page_id if needed
    while (page_id >= index_dm_->GetNumPages()) {
        int pid;
        index_bpm_->NewPage(&pid);
        index_bpm_->UnpinPage(pid, false);
    }

    char* data = index_bpm_->FetchPage(page_id);
    if (!data) throw std::runtime_error("KDTreeDisk: Buffer pool exhausted on WriteNode.");

    std::memcpy(data + offset, &node, sizeof(KDNode));
    index_bpm_->UnpinPage(page_id, true);   // true = dirty
}

KDNode KDTreeDisk::ReadNode(int node_id) const {
    int page_id = node_id / nodes_per_page_;
    int offset  = (node_id % nodes_per_page_) * sizeof(KDNode);

    char* data = index_bpm_->FetchPage(page_id);
    if (!data) throw std::runtime_error("KDTreeDisk: Buffer pool exhausted on ReadNode.");

    KDNode node;
    std::memcpy(&node, data + offset, sizeof(KDNode));
    index_bpm_->UnpinPage(page_id, false);  // false = not dirty
    return node;
}

void KDTreeDisk::BuildIndex() {
    total_nodes_ = 0;
    int total = data_file_->GetTotalRecords();
    if (total == 0) return;

    std::vector<int> ids(total);
    std::iota(ids.begin(), ids.end(), 0);
    root_node_id_ = BuildRecursive(ids, 0, total, 0);

    // Flush index to disk after full build
    index_bpm_->FlushAll();
}

int KDTreeDisk::BuildRecursive(std::vector<int>& ids, int start, int end, int depth) {
    if (start >= end) return -1;

    int axis = depth % dims_;
    int mid  = start + (end - start) / 2;

    std::nth_element(ids.begin() + start,
                     ids.begin() + mid,
                     ids.begin() + end,
        [&](int a, int b) {
            return data_file_->ReadRecord(a)[axis] < data_file_->ReadRecord(b)[axis];
        });

    int current_id = total_nodes_++;

    KDNode node;
    node.record_id     = ids[mid];
    node.axis          = axis;
    node.left_node_id  = BuildRecursive(ids, start, mid,   depth + 1);
    node.right_node_id = BuildRecursive(ids, mid + 1, end, depth + 1);

    WriteNode(current_id, node);
    return current_id;
}

// ── KNN Search ────────────────────────────────────────────────────────────────

static float EuclideanDist(const std::vector<float>& a, const std::vector<float>& b) {
    float sum = 0;
    for (int i = 0; i < (int)a.size(); i++)
        sum += (a[i] - b[i]) * (a[i] - b[i]);
    return std::sqrt(sum);
}

std::vector<int> KDTreeDisk::KNNSearch(const std::vector<float>& query, int k) const {
    std::priority_queue<std::pair<float,int>> pq;
    KNNSearchRecursive(query, root_node_id_, pq, k);

    std::vector<int> results;
    while (!pq.empty()) {
        results.push_back(pq.top().second);
        pq.pop();
    }
    std::reverse(results.begin(), results.end());
    return results;
}

void KDTreeDisk::KNNSearchRecursive(const std::vector<float>& query, int node_id,
                                     std::priority_queue<std::pair<float,int>>& pq,
                                     int k) const {
    if (node_id == -1) return;

    KDNode node = ReadNode(node_id);
    std::vector<float> train = data_file_->ReadRecord(node.record_id);

    float dist = EuclideanDist(query, train);
    pq.push({dist, node.record_id});
    if ((int)pq.size() > k) pq.pop();

    int axis     = node.axis;
    bool go_left = (query[axis] < train[axis]);
    int next     = go_left ? node.left_node_id  : node.right_node_id;
    int other    = go_left ? node.right_node_id : node.left_node_id;

    KNNSearchRecursive(query, next, pq, k);

    float axis_dist = std::abs(query[axis] - train[axis]);
    if ((int)pq.size() < k || axis_dist < pq.top().first)
        KNNSearchRecursive(query, other, pq, k);
}