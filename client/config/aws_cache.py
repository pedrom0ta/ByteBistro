from django.core.cache.backends.db import DatabaseCache
from django.db import connections, router, transaction


class PostgresCache(DatabaseCache):
    def incr(self, key, delta=1, version=None):
        # DatabaseCache's default read/modify/write increment is not atomic.
        alias = router.db_for_write(self.cache_model_class)
        with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [self.make_key(key, version=version)],
            )
            return super().incr(key, delta, version)
