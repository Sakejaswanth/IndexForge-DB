#include "lru_replacer.h"

LRUReplacer::LRUReplacer(int num_frames) : capacity_(num_frames) {}

bool LRUReplacer::Evict(int* frame_id) {
    if (lru_list_.empty()) return false;
    // Back of list = least recently used
    *frame_id = lru_list_.back();
    frame_map_.erase(*frame_id);
    lru_list_.pop_back();
    return true;
}

int LRUReplacer::Evict() {
    int fid = -1;
    if (Evict(&fid)) return fid;
    return -1;
}

void LRUReplacer::RecordAccess(int frame_id) {
    auto it = frame_map_.find(frame_id);
    if (it != frame_map_.end()) {
        // Already tracked — move to front (MRU position)
        lru_list_.erase(it->second);
        frame_map_.erase(it);
    }
    lru_list_.push_front(frame_id);
    frame_map_[frame_id] = lru_list_.begin();
}

void LRUReplacer::Remove(int frame_id) {
    auto it = frame_map_.find(frame_id);
    if (it != frame_map_.end()) {
        lru_list_.erase(it->second);
        frame_map_.erase(it);
    }
}

int LRUReplacer::Size() const {
    return static_cast<int>(lru_list_.size());
}