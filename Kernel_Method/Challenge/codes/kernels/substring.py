from collections import defaultdict

import numpy as np
from tqdm import tqdm
import itertools


class TrieNode:
    def __init__(self, depth=0):
        self.depth = depth
        self.counts = {}
        self.children = defaultdict(self.create_child)

    def create_child(self):
        return TrieNode(depth=self.depth + 1)

    def is_leaf(self):
        return len(self.children) == 0

    def __iter__(self):
        yield self

        for child in self.children.values():
            for grandchild in child:
                yield grandchild


##########################################################
class Trie:
    def __init__(self, seq_size):
        self.root = TrieNode()
        self.seq_size = seq_size

    def add(self, id, s, jumps):
        node = self.root
        for c in s:
            node = node.children[c]

        if id not in node.counts:
            node.counts[id] = jumps
        else:
            node.counts[id] = min(node.counts[id], jumps)

    @property
    def nodes(self):
        for node in self.root:
            yield node

    @property
    def num_nodes(self):
        return sum(1 for _ in self.nodes)

    @property
    def leaves(self):
        for node in self.nodes:
            if node.is_leaf():
                yield node

    @property
    def num_leaves(self):
        return sum(1 for _ in self.leaves)


class SubStringKernel:

    def __init__(self, k, jump, weight=None):
        self.k = k
        self.jump = jump
        self.weight = weight
        self.trie = Trie(k)

        self.next_id = 0
        self.fitted_sequences = {}

        self.fitted_ = False
        self.fitted_on_ = None

    def fit(self, S):
        for s in tqdm(S):
            self._fit_string(s)

        self.fitted_ = True
        self.fitted_on_ = S

        return self._build_kernel(S, self.fitted_on_)

    def predict(self, T):
        for t in T:
            self._fit_string(t)

        return self._build_kernel(T, self.fitted_on_)

    def _fit_string(self, s):
        if s in self.fitted_sequences:
            return
        id = self.next_id
        self.next_id += 1
        self.fitted_sequences[s] = id

        iterable = np.arange(0, self.jump + self.k)  # start at one because 0 is always selected
        for full_sub in self._substrings(s, self.k + self.jump):
            for sub_idx in itertools.combinations(iterable, self.k):
                if sub_idx[0] == 0:  # the first element is always takken (to avoid repetition)
                    sub, jumps = self._make_sub(full_sub, sub_idx)  # number of gap
                    self.trie.add(id, sub, len(sub) + jumps)

    def _build_kernel(self, T, S):
        T_ids = [
            self.fitted_sequences[t]
            for t in T
        ]

        S_ids = [
            self.fitted_sequences[s]
            for s in S
        ]

        dot_products = defaultdict(float)
        squared_norms = defaultdict(float)

        weight = self.weight or 1.0
        set_T_ids = set(T_ids)
        set_S_ids = set(S_ids)
        all_ids = set_T_ids | set_S_ids

        it = dict(iterable=self.trie.leaves, total=self.trie.num_leaves)

        for node in tqdm(**it):
            node_ids = set(node.counts.keys())

            for idx in node_ids & all_ids:
                squared_norms[idx] += weight ** (2 * node.counts[idx])

            for t_idx in node_ids & set_T_ids:
                for s_idx in node_ids & set_S_ids:
                    dot_product = weight ** (node.counts[t_idx] + node.counts[s_idx])
                    dot_products[t_idx, s_idx] += dot_product

        K = np.zeros((len(T), len(S)))

        for i, t_idx in enumerate(T_ids):
            for j, s_idx in enumerate(S_ids):
                K[i, j] = dot_products[t_idx, s_idx] / np.sqrt(squared_norms[t_idx] * squared_norms[s_idx])

        return K

    @staticmethod
    def _substrings(s, k):
        return [
            s[i:i + k]
            for i in range(len(s) - k + 1)
        ]

    @staticmethod
    def _make_sub(full_sub, sub_idx):
        sub = full_sub[sub_idx[0]]
        jumps = 0
        for i in range(1, len(sub_idx)):
            sub += full_sub[sub_idx[i]]
            if sub_idx[i] != sub_idx[i - 1] + 1:
                jumps += 1

        return sub, jumps

# Potential improvement : direclty guessing nbjump