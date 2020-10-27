import time
from collections import deque, Counter

class Cache:
    """
    Used for managing cache rotation & retention, max len
    """
    def __init__(self, parent, **kw):
        self.parent = parent
        self.cache = {}
        self.log = self.parent.log
        self.timestamp_to_cache = {}
        self.access_history = deque()
        self.max_len = self.parent.max_cache_len
    def check_max_len_and_clear(self):
        if len(self.timestamp_to_cache) >= self.max_len:
            while len(self.timestamp_to_cache) >= self.max_len:
                cache_time = self.access_history.popleft()
                if cache_time in self.timestamp_to_cache:
                    _, cache_key = self.timestamp_to_cache[cache_time]
                    del self.timestamp_to_cache[cache_time]
                    if cache_key in self.cache and not self.cache[cache_key] == cache_time:
                        continue
                    del self.cache[cache_key]
                    self.log.debug(f"# {self.parent} cach_key '{cache_key}' cleared due to cache length of {self.max_len} exceeded")
    def update_timestamp(self, cached_key):
        if cached_key in self:
            old_time = self.cache[cached_key]
            new_time = time.time()
            self.timestamp_to_cache[new_time] = self.timestamp_to_cache[old_time]
            del self.timestamp_to_cache[old_time]
            self.cache[cached_key] = new_time
            self.access_history.append(new_time)
    def __iter__(self):
        def cache_generator():
            for cache_key, timestamp in self.cache.copy().items():
                yield cache_key, self.timestamp_to_cache[timestamp][0]
        return cache_generator()
    def __getitem__(self, cached_key):
        if cached_key in self:
            cache_time = self.cache[cached_key]
            if cache_time in self.timestamp_to_cache:
                cache_row = self.timestamp_to_cache[cache_time][0]
                self.update_timestamp(cached_key)
                return cache_row
        return None
    def __setitem__(self, cached_key, row):
        cache_time = time.time()
        if cached_key in self.cache:
            old_cache_time = self.cache[cached_key]
            del self.timestamp_to_cache[old_cache_time]
        self.cache[cached_key] = cache_time
        self.timestamp_to_cache[cache_time] = [row, cached_key]
        self.access_history.append(cache_time)
        self.check_max_len_and_clear()
    def __delitem__(self, cached_key):
        if cached_key in self.cache:
            cache_time = self.cache.pop(cached_key)
            if cache_time in self.timestamp_to_cache:
                del self.timestamp_to_cache[cache_time]
    def __contains__(self, cached_key):
        return cached_key in self.cache