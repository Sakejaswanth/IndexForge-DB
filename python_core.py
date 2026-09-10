"""
python_core.py
Pure-Python fallback implementation of `sqlmates_core` and `rtree_core`.
Provides identical APIs so the application and benchmarking run seamlessly
even on systems or hosting environments without C++ build tools.
"""

import os
import time
import struct
import math
import heapq
import numpy as np

PAGE_SIZE = 4096

class PythonDataFile:
    """Disk-backed vector storage compatible with C++ DataFile layout."""
    def __init__(self, file_path: str, dims: int):
        self.file_path = file_path
        self.dims = dims
        self.record_size = dims * 4
        self.records_per_page = max(1, (PAGE_SIZE - 4) // self.record_size)
        self.records = []
        self._load_or_init()

    def _load_or_init(self):
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) < PAGE_SIZE:
            self.records = []
            return

        try:
            with open(self.file_path, "rb") as f:
                header = f.read(PAGE_SIZE)
                if len(header) < 8:
                    return
                total_records, total_pages = struct.unpack_from("ii", header, 0)
                records = []
                for p in range(total_pages):
                    page_bytes = f.read(PAGE_SIZE)
                    if len(page_bytes) < PAGE_SIZE:
                        break
                    count = struct.unpack_from("i", page_bytes, 0)[0]
                    offset = 4
                    for _ in range(count):
                        vec = struct.unpack_from(f"{self.dims}f", page_bytes, offset)
                        records.append(list(vec))
                        offset += self.record_size
                        if len(records) >= total_records:
                            break
                    if len(records) >= total_records:
                        break
                self.records = records
        except Exception:
            self.records = []

    def save(self):
        parent = os.path.dirname(os.path.abspath(self.file_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        total_records = len(self.records)
        total_pages = math.ceil(total_records / self.records_per_page) if total_records > 0 else 0

        with open(self.file_path, "wb") as f:
            # Page 0: header
            header = bytearray(PAGE_SIZE)
            struct.pack_into("ii", header, 0, total_records, total_pages)
            f.write(header)

            # Data pages
            for p in range(total_pages):
                page = bytearray(PAGE_SIZE)
                start = p * self.records_per_page
                end = min(start + self.records_per_page, total_records)
                count = end - start
                struct.pack_into("i", page, 0, count)
                offset = 4
                for i in range(start, end):
                    struct.pack_into(f"{self.dims}f", page, offset, *self.records[i])
                    offset += self.record_size
                f.write(page)

    def append(self, vec):
        rid = len(self.records)
        self.records.append(list(vec))
        return rid

    def get(self, rid):
        return self.records[rid]


class KDNode:
    __slots__ = ('record_id', 'axis', 'left', 'right')
    def __init__(self, record_id, axis):
        self.record_id = record_id
        self.axis = axis
        self.left = None
        self.right = None


class IndexEngine:
    """Pure-Python drop-in replacement for sqlmates_core.IndexEngine."""
    def __init__(self, data_path: str, index_path: str, dims: int):
        self.data_path = data_path
        self.index_path = index_path
        self.dims = dims
        self.data_file = PythonDataFile(data_path, dims)
        self.root = None
        if self.data_file.records:
            self.build_index()

    def insert_vectors(self, vecs):
        for v in vecs:
            self.data_file.append(v)
        self.data_file.save()

    def build_index(self):
        n = len(self.data_file.records)
        if n == 0:
            self.root = None
            return

        ids = list(range(n))
        records = np.array(self.data_file.records, dtype=np.float32)

        def _build(sub_ids, depth):
            if len(sub_ids) == 0:
                return None
            axis = depth % self.dims
            sub_ids.sort(key=lambda idx: records[idx, axis])
            mid = len(sub_ids) // 2
            node = KDNode(sub_ids[mid], axis)
            node.left = _build(sub_ids[:mid], depth + 1)
            node.right = _build(sub_ids[mid + 1:], depth + 1)
            return node

        self.root = _build(ids, 0)

    def get_total_records(self) -> int:
        return len(self.data_file.records)

    def knn_search(self, query: list, k: int) -> dict:
        q = np.array(query, dtype=np.float32)
        records = np.array(self.data_file.records, dtype=np.float32)
        n = len(records)
        if n == 0:
            return {
                "linear_time_us": 0,
                "kdtree_time_us": 0,
                "record_ids": [],
                "coordinates": [],
            }

        k = min(k, n)

        # 1. Linear scan baseline
        t0 = time.perf_counter_ns()
        diff = records - q
        dist_sq = np.sum(diff * diff, axis=1)
        if k < n:
            linear_indices = np.argpartition(dist_sq, k)[:k]
            linear_indices = linear_indices[np.argsort(dist_sq[linear_indices])]
        else:
            linear_indices = np.argsort(dist_sq)
        t1 = time.perf_counter_ns()
        linear_time_us = max(1, (t1 - t0) // 1000)

        # 2. KD-Tree branch-and-bound search
        t2 = time.perf_counter_ns()
        heap = []

        def _search(node):
            if node is None:
                return
            rid = node.record_id
            rec = records[rid]
            d = math.sqrt(float(np.sum((rec - q) ** 2)))

            if len(heap) < k:
                heapq.heappush(heap, (-d, rid))
            elif d < -heap[0][0]:
                heapq.heapreplace(heap, (-d, rid))

            axis = node.axis
            diff_axis = q[axis] - rec[axis]
            go_left = diff_axis < 0
            first, second = (node.left, node.right) if go_left else (node.right, node.left)

            _search(first)

            worst_dist = -heap[0][0] if len(heap) == k else float('inf')
            if abs(diff_axis) < worst_dist:
                _search(second)

        _search(self.root)

        sorted_heap = sorted([(-item[0], item[1]) for item in heap], key=lambda x: x[0])
        tree_results = [item[1] for item in sorted_heap]
        t3 = time.perf_counter_ns()
        tree_time_us = max(1, (t3 - t2) // 1000)

        result_coords = [self.data_file.get(rid) for rid in tree_results]

        return {
            "linear_time_us": int(linear_time_us),
            "kdtree_time_us": int(tree_time_us),
            "record_ids": tree_results,
            "coordinates": result_coords,
        }


class RTreeNodePy:
    __slots__ = ('is_leaf', 'entries')
    def __init__(self, is_leaf=True):
        self.is_leaf = is_leaf
        self.entries = []


class RTreeEngine:
    """Pure-Python drop-in replacement for rtree_core.RTreeEngine."""
    def __init__(self, data_path: str, tree_path: str, dims: int):
        self.data_path = data_path
        self.tree_path = tree_path
        self.dims = dims
        self.data_file = PythonDataFile(data_path, dims)
        self.records = self.data_file.records
        self.max_entries = max(4, (PAGE_SIZE - 8) // (2 * dims * 4 + 4))
        self.min_entries = max(2, self.max_entries * 2 // 5)
        self.root = RTreeNodePy(is_leaf=True)
        if self.records:
            self._rebuild_tree()

    def _rebuild_tree(self):
        self.root = RTreeNodePy(is_leaf=True)
        for rid, vec in enumerate(self.records):
            self._insert_record(rid, vec)

    def insert_vectors(self, vecs):
        for v in vecs:
            rid = self.data_file.append(v)
            self._insert_record(rid, v)
        self.data_file.save()

    def _insert_record(self, rid: int, vec: list):
        pt = np.array(vec, dtype=np.float32)
        sibling = self._insert(self.root, rid, pt)
        if sibling is not None:
            old_root = self.root
            self.root = RTreeNodePy(is_leaf=False)
            self.root.entries = [
                self._compute_mbr(old_root),
                self._compute_mbr(sibling),
            ]

    def _insert(self, node: RTreeNodePy, rid: int, pt: np.ndarray):
        if node.is_leaf:
            node.entries.append((pt.copy(), pt.copy(), rid))
        else:
            best_index = min(
                range(len(node.entries)),
                key=lambda index: self._enlargement(node.entries[index], pt),
            )
            child = node.entries[best_index][2]
            sibling = self._insert(child, rid, pt)
            node.entries[best_index] = self._compute_mbr(child)
            if sibling is not None:
                node.entries.append(self._compute_mbr(sibling))

        if len(node.entries) > self.max_entries:
            return self._split(node)
        return None

    def _enlargement(self, entry, pt: np.ndarray) -> float:
        min_b, max_b, _ = entry
        new_min = np.minimum(min_b, pt)
        new_max = np.maximum(max_b, pt)
        cur_vol = float(np.prod(np.maximum(0, max_b - min_b)))
        new_vol = float(np.prod(np.maximum(0, new_max - new_min)))
        return new_vol - cur_vol

    def _split(self, node: RTreeNodePy):
        entries = node.entries
        mids = []
        for min_b, max_b, _ in entries:
            mids.append((min_b + max_b) * 0.5)
        mids = np.array(mids)
        split_axis = int(np.argmax(np.var(mids, axis=0)))
        entries.sort(key=lambda e: (e[0][split_axis] + e[1][split_axis]) * 0.5)
        mid = len(entries) // 2

        g1 = entries[:mid]
        g2 = entries[mid:]

        node.entries = g1
        sibling = RTreeNodePy(is_leaf=node.is_leaf)
        sibling.entries = g2
        return sibling

    def _compute_mbr(self, node: RTreeNodePy):
        mins = np.min([e[0] for e in node.entries], axis=0)
        maxs = np.max([e[1] for e in node.entries], axis=0)
        return (mins, maxs, node)

    def get_total_records(self) -> int:
        return len(self.data_file.records)

    def get_tree_height(self) -> int:
        h = 1
        curr = self.root
        while not curr.is_leaf and curr.entries:
            h += 1
            curr = curr.entries[0][2]
        return h

    def knn_search(self, query: list, k: int) -> dict:
        q = np.array(query, dtype=np.float32)
        records = np.array(self.data_file.records, dtype=np.float32)
        n = len(records)
        if n == 0:
            return {
                "linear_time_us": 0,
                "rtree_time_us": 0,
                "record_ids": [],
                "coordinates": [],
                "pages_read": 0,
                "tree_height": self.get_tree_height(),
            }

        k = min(k, n)

        # 1. Linear scan baseline
        t0 = time.perf_counter_ns()
        diff = records - q
        dist_sq = np.sum(diff * diff, axis=1)
        if k < n:
            linear_indices = np.argpartition(dist_sq, k)[:k]
            linear_indices = linear_indices[np.argsort(dist_sq[linear_indices])]
        else:
            linear_indices = np.argsort(dist_sq)
        t1 = time.perf_counter_ns()
        linear_time_us = max(1, (t1 - t0) // 1000)

        # 2. R-Tree MINDIST priority queue search
        t2 = time.perf_counter_ns()
        pq = []
        pages_read = 1

        def _mindist_sq(min_b, max_b):
            r = np.clip(q, min_b, max_b)
            d = q - r
            return float(np.sum(d * d))

        if self.root.entries:
            mins = np.min([e[0] for e in self.root.entries], axis=0)
            maxs = np.max([e[1] for e in self.root.entries], axis=0)
            heapq.heappush(pq, (_mindist_sq(mins, maxs), True, self.root))

        results = []
        while pq and len(results) < k:
            d_sq, is_node, obj = heapq.heappop(pq)
            if not is_node:
                results.append((obj, d_sq))
            else:
                pages_read += 1
                for min_b, max_b, child in obj.entries:
                    dist = _mindist_sq(min_b, max_b)
                    if obj.is_leaf:
                        heapq.heappush(pq, (dist, False, child))
                    else:
                        heapq.heappush(pq, (dist, True, child))

        record_ids = [r[0] for r in results]
        t3 = time.perf_counter_ns()
        rtree_time_us = max(1, (t3 - t2) // 1000)

        coordinates = [self.data_file.get(rid) for rid in record_ids]

        return {
            "linear_time_us": int(linear_time_us),
            "rtree_time_us": int(rtree_time_us),
            "record_ids": record_ids,
            "coordinates": coordinates,
            "pages_read": pages_read,
            "tree_height": self.get_tree_height(),
        }
