"""Fixed five-GSD positive/explicit-target-removed engineering capture group."""


async def run(owner, token, runtime=None):
    from .paired_transaction_v2 import run as run_transaction
    return await run_transaction(owner, token, [[.5, 1., 2., 3., 4.]], 0, runtime, dataset=True)
