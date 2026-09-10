#ifndef LRU_REPLACER_H
#define LRU_REPLACER_H

#include <list>
#include <unordered_map>

class LRUReplacer {
public:
    explicit LRUReplacer(int num_frames);
    ~LRUReplacer() = default;


    bool Evict(int* frame_id);
    int Evict();

    void RecordAccess(int frame_id);
    void Insert(int frame_id) { RecordAccess(frame_id); }

    void Remove(int frame_id);

    int Size() const;

private:
    int capacity_;
    // LRU list: front = MRU, back = LRU
    std::list<int> lru_list_;
    // frame_id → iterator into lru_list_
    std::unordered_map<int, std::list<int>::iterator> frame_map_;
};

#endif  // LRU_REPLACER_H