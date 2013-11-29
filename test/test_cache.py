
from heapq import heappush, heappop
import random
import unittest

from keepnote.cache import LRUDict


class CacheTest(unittest.TestCase):
    def __init__(self):
        h = []
        heappush(h, 2)
        heappush(h, 5)
        heappush(h, 1)
        heappush(h, 9)
        heappush(h, 1)

        print h

        while h:
            print heappop(h)

        c = LRUDict(10)
        for i in xrange(100):
            c[str(i)] = i

        print c
        print c._ages
        print c._age_lookup

        c = LRUCache(lambda x: int(x), 10)

        for i in range(100):
            j = str(random.randint(0, 20))
            print c[j]

        print c._cache_dict
        print c._cache_dict._ages
