from couchbase.auth import PasswordAuthenticator
from acouchbase.cluster import Cluster

from couchbase.options import ClusterOptions

from mite.datapools import IterableDataPool


datapool = IterableDataPool([(f"mitekey_{i}",) for i in range(1_000_000)])


async def get_couchbase():
    print("CREATING COUCHBASE CONNECTION!!!")
    username = "mite"
    password = "mitemite"
    bucket_name = "mite"

    cluster = Cluster(
        "couchbase://127.0.0.1",
        ClusterOptions(PasswordAuthenticator(username, password)),
    )

    cb = cluster.bucket(bucket_name)

    cb_coll = cb.scope("_default").collection("_default")

    return cb_coll


def mite_couchbase(label=None):
    def decorator(fn):
        # _fixture will classify this function as a needing a fixture
        # to be created before the test runs
        fn._fixture = True
        # _fixture_label will be used to identify the fixture and be used as the
        # key in the fixture registry
        fn._fixture_label = label or fn.__name__
        # _fixture_func will be the function that creates the fixture
        fn._fixture_func = get_couchbase
        # _fixture_variable will be the variable name that will be used to
        # store the fixture in the context
        fn._fixture_variable = "couchbase"

        return fn

    return decorator


@mite_couchbase(label="journey")
async def journey(ctx, key):
    print("inside journey")
    await ctx.couchbase.upsert(key, {"test": "test_value"})


def scenario():
    return [
        ["cbtest:journey", datapool, lambda s, e: 5],
        ["cbtest:journey", datapool, lambda s, e: 2],
    ]
