#ifndef SEARCH_ENGINE_H
#define SEARCH_ENGINE_H

#include "data_file.h"
#include <vector>
#include <chrono>

class SearchEngine {
public:
    static std::vector<int> LinearSearchKNN(DataFile* data_file, const std::vector<float>& query, int k);

    template <typename Func>
    static long long MeasureTimeMicroseconds(Func func) {
        auto start = std::chrono::high_resolution_clock::now();
        func();
        auto end = std::chrono::high_resolution_clock::now();
        return std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    }
};

#endif