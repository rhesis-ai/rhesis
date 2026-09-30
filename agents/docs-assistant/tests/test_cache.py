import asyncio

import pytest

from docs_assistant.corpus.cache import DocsUnavailable


async def test_first_get_loads_the_snapshot(cache, site):
    assert cache.status() == "unavailable"
    snapshot = await cache.get()
    assert len(snapshot.pages) == 8
    assert cache.status() == "ready"
    assert site.requests.count("/llms-full.txt") == 1


async def test_get_within_ttl_does_not_refetch(cache, site, clock):
    await cache.get()
    clock.now += 100
    await cache.get()
    assert site.requests.count("/llms-full.txt") == 1


async def test_expired_snapshot_is_served_while_a_background_refresh_runs(cache, site, clock):
    first = await cache.get()
    clock.now += 3601
    assert await cache.get() is first
    await asyncio.sleep(0)
    await cache._refresh_task
    assert site.requests.count("/llms-full.txt") == 2
    assert not cache.expired


async def test_unchanged_docs_keep_the_same_snapshot_but_a_new_timestamp(cache, clock):
    first = await cache.get()
    stamp = first.fetched_at
    clock.now += 3601
    assert await cache.refresh()
    assert cache.snapshot is first
    assert first.fetched_at >= stamp


async def test_changed_docs_rebuild_the_snapshot(cache, site, clock):
    first = await cache.get()
    site.llms_full = site.llms_full.replace("Metric scope", "Metric scopes", 1)
    assert await cache.refresh()
    assert cache.snapshot is not first


async def test_site_down_with_a_snapshot_goes_stale(cache, site, clock):
    await cache.get()
    site.down = True
    clock.now += 3601
    assert not await cache.refresh()
    assert cache.stale
    assert cache.status() == "stale"
    # Answers still work from the old snapshot.
    assert (await cache.get()).page("sdk/installation") is not None


async def test_site_down_with_no_snapshot_is_unavailable(cache, site):
    site.down = True
    with pytest.raises(DocsUnavailable):
        await cache.get()
    assert cache.status() == "unavailable"
