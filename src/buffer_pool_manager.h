#ifndef BUFFER_POOL_MANAGER_H
#define BUFFER_POOL_MANAGER_H

#include "disk_manager.h"
#include "page.h"
#include <unordered_map>
#include <list>
#include <vector>
#include <stdexcept>

#include "lru_replacer.h"

struct Frame {
    char data[PAGE_SIZE];
    int  page_id    = -1;
    int  pin_count  = 0;
    bool is_dirty   = false;
};

class BufferPoolManager {
public:
    BufferPoolManager(DiskManager* dm, int pool_size);
    ~BufferPoolManager();

    // Pin a page into the pool; returns pointer to its data buffer.
    // Caller MUST call UnpinPage when done.
    char* FetchPage(int page_id);

    // Allocate a new disk page, bring it into the pool pinned.
    // Writes the assigned page_id into *page_id_out.
    char* NewPage(int* page_id_out);

    // Release the caller's pin. Set is_dirty=true if the page was modified.
    void UnpinPage(int page_id, bool is_dirty);

    // Force a page to disk immediately (does not evict).
    void FlushPage(int page_id);

    // Flush every dirty page to disk.
    void FlushAll();

    // Statistics
    int GetHitCount() const { return hit_count_; }
    int GetMissCount() const { return miss_count_; }
    void ResetStats() { hit_count_ = 0; miss_count_ = 0; }

private:
    DiskManager* dm_;
    int pool_size_;
    std::vector<Frame> frames_;
    std::unordered_map<int, int> page_table_; // page_id -> frame_id
    LRUReplacer replacer_;
    std::list<int> free_list_; // frame_ids not yet used
    int hit_count_ = 0;
    int miss_count_ = 0;

    // Find a victim frame (from free list, then LRU). Flushes if dirty.
    // Returns frame_id, or throws if pool is exhausted.
    int GetFreeFrame();
};

#endif // BUFFER_POOL_MANAGER_H
