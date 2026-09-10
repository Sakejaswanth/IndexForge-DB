#ifndef KDTREE_DISK_H
#define KDTREE_DISK_H

#include "disk_manager.h"
#include "buffer_pool_manager.h"
#include "data_file.h"
#include <vector>
#include <queue>
#include <cmath>

struct KDNode {
    int record_id;      // index into DataFile
    int left_node_id;   // -1 if leaf
    int right_node_id;  // -1 if leaf
    int axis;           // split dimension
};

class KDTreeDisk {
private:
    DiskManager*       index_dm_;
    BufferPoolManager* index_bpm_;
    DataFile*          data_file_;
    int dims_;
    int nodes_per_page_;
    int total_nodes_;
    int root_node_id_;

    void   WriteNode(int node_id, const KDNode& node);
    KDNode ReadNode(int node_id) const;

    int  BuildRecursive(std::vector<int>& ids, int start, int end, int depth);
    void KNNSearchRecursive(const std::vector<float>& query, int node_id,
                            std::priority_queue<std::pair<float,int>>& pq, int k) const;

public:
    KDTreeDisk(DiskManager* index_dm, BufferPoolManager* index_bpm,
               DataFile* data_file, int dims);

    void BuildIndex();
    std::vector<int> KNNSearch(const std::vector<float>& query, int k) const;
};

#endif  