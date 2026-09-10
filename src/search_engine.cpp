#include "search_engine.h"
#include <queue>
#include <cmath>
#include <algorithm>

std::vector<int> SearchEngine::LinearSearchKNN(DataFile* data_file, const std::vector<float>& query, int k) {
    std::priority_queue<std::pair<float, int>> pq;
    int total_records = data_file->GetTotalRecords();

    for (int i = 0; i < total_records; i++) {
        std::vector<float> vec = data_file->ReadRecord(i);

        float sum_sq = 0.0f;
        for (size_t d = 0; d < query.size(); d++) {
            float diff = query[d] - vec[d];
            sum_sq += diff * diff;
        }
        float dist = std::sqrt(sum_sq);
        
        pq.push({dist, i});
        if ((int)pq.size() > k) {
            pq.pop();
        }
    }

    std::vector<int> results;
    while (!pq.empty()) {
        results.push_back(pq.top().second);
        pq.pop();
    }
    
    // Reverse so the closest is first (matches KD-Tree behavior)
    std::reverse(results.begin(), results.end());
    
    return results;
}