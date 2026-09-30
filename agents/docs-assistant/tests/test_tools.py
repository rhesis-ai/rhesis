from dataclasses import replace

from docs_assistant.context import TurnContext
from docs_assistant.schemas import AnswerDraft
from docs_assistant.tools import (
    ACCEPTED,
    BUDGET_EXHAUSTED,
    NOT_FOUND,
    REJECTED,
    fetch_page_impl,
    get_changelog_impl,
    list_sections_impl,
    render_page,
    search_docs_impl,
    submit_answer_impl,
)
from tests.mocks import draft

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"


async def test_fetch_adds_the_page_to_the_ledger_but_search_does_not(ctx):
    result = search_docs_impl(ctx, "metric scope")
    assert "NOT citable" in result
    assert ctx.ledger == {}
    assert ctx.search_hits
    page = await fetch_page_impl(ctx, "docs/metrics/metric-scope.md")
    assert page.startswith(f'<doc url="{SCOPE}"')
    assert list(ctx.ledger) == [SCOPE]


async def test_fetch_lists_headings_with_citable_anchors(ctx):
    result = await fetch_page_impl(ctx, SCOPE)
    assert f"cite as {SCOPE}#anchor" in result
    assert "#when-to-use-multi-turn" in result
    assert "Links on this page:" in result


async def test_fetching_the_same_page_twice_counts_one_page(ctx):
    await fetch_page_impl(ctx, SCOPE)
    await fetch_page_impl(ctx, SCOPE + "#planning-checklist")
    assert ctx.budget.pages == 1
    assert ctx.budget.tool_calls == 2


async def test_page_budget(ctx):
    ctx = replace(ctx, settings=replace(ctx.settings, max_pages=1))
    await fetch_page_impl(ctx, SCOPE)
    result = await fetch_page_impl(ctx, "sdk/installation")
    assert result.startswith(BUDGET_EXHAUSTED)
    assert "page_budget" in ctx.limits_hit
    assert list(ctx.ledger) == [SCOPE]


async def test_tool_and_search_budgets(ctx):
    ctx = replace(ctx, settings=replace(ctx.settings, max_tool_calls=3, max_searches=1))
    search_docs_impl(ctx, "install")
    assert search_docs_impl(ctx, "install").startswith(BUDGET_EXHAUSTED)
    assert "search_budget" in ctx.limits_hit
    list_sections_impl(ctx)
    assert (await fetch_page_impl(ctx, SCOPE)).startswith(BUDGET_EXHAUSTED)
    assert "tool_budget" in ctx.limits_hit


async def test_unknown_page_suggests_the_closest(ctx):
    result = await fetch_page_impl(ctx, "sdk/install-guide")
    assert result.startswith(NOT_FOUND)
    assert "https://docs.rhesis.ai/sdk/installation" in result
    assert ctx.ledger == {}


async def test_section_anchor_returns_that_part_of_the_page(ctx):
    result = await fetch_page_impl(ctx, "self-hosting/docker-compose", "database-backup")
    body = result.split("\n---\n", 1)[1]
    assert "Database Backup" in body
    assert "Production Setup" not in body


def test_long_pages_are_cut_with_a_hint(snapshot):
    page = snapshot.page("self-hosting/docker-compose")
    result = render_page(page, None, window=500)
    assert "[Page truncated." in result
    assert len(result.split("\n---\n", 1)[1]) < 900


async def test_index_only_pages_are_fetched_live(snapshot, settings, cache, site):
    await cache.get()
    ctx = TurnContext(snapshot=cache.snapshot, settings=settings, cache=cache)
    result = await fetch_page_impl(ctx, "glossary/hallucination")
    assert "fabricated, or nonsensical" in result
    assert "https://docs.rhesis.ai/glossary/hallucination" in ctx.ledger
    assert "/api/md/glossary/hallucination" in site.requests


async def test_expired_snapshot_pages_are_refetched_live_with_fallback(
    settings, cache, site, clock
):
    await cache.get()
    clock.now += 3601
    ctx = TurnContext(snapshot=cache.snapshot, settings=settings, cache=cache)
    await fetch_page_impl(ctx, "sdk/installation")
    assert "/api/md/sdk/installation" in site.requests
    site.down = True
    ctx = TurnContext(snapshot=cache.snapshot, settings=settings, cache=cache)
    result = await fetch_page_impl(ctx, "sdk/metrics")
    assert result.startswith('<doc url="https://docs.rhesis.ai/sdk/metrics" title="Overview">')
    assert ctx.ledger["https://docs.rhesis.ai/sdk/metrics"] is cache.snapshot.page("sdk/metrics")


def test_changelog_counts_as_reading_its_page(ctx):
    result = get_changelog_impl(ctx)
    assert "cite as https://docs.rhesis.ai/changelog#" in result
    assert "https://docs.rhesis.ai/changelog" in ctx.ledger
    assert get_changelog_impl(ctx, version="99.0.0") == "No matching changelog entries."


async def test_changelog_respects_the_page_budget(ctx):
    ctx = replace(ctx, settings=replace(ctx.settings, max_pages=1))
    await fetch_page_impl(ctx, SCOPE)
    assert get_changelog_impl(ctx).startswith(BUDGET_EXHAUSTED)
    assert "page_budget" in ctx.limits_hit
    assert list(ctx.ledger) == [SCOPE]
    assert ctx.budget.pages == 1


async def test_rereading_the_changelog_costs_no_page(ctx):
    ctx = replace(ctx, settings=replace(ctx.settings, max_pages=1))
    get_changelog_impl(ctx)
    assert "cite as" in get_changelog_impl(ctx, since="0.1.0")
    assert ctx.budget.pages == 1
    assert (await fetch_page_impl(ctx, SCOPE)).startswith(BUDGET_EXHAUSTED)


def test_list_sections(ctx):
    assert "sdk (2)" in list_sections_impl(ctx)
    listing = list_sections_impl(ctx, "self_hosting")
    assert "https://docs.rhesis.ai/self-hosting/docker-compose" in listing
    assert list_sections_impl(ctx, "contribute") == "No pages in section contribute."


async def test_submit_accepts_a_grounded_draft(ctx):
    await fetch_page_impl(ctx, SCOPE)
    assert submit_answer_impl(ctx, AnswerDraft(**draft())) == ACCEPTED
    assert ctx.accepted is not None


def test_submit_rejects_with_numbered_problems(ctx):
    result = submit_answer_impl(ctx, AnswerDraft(**draft()))
    assert result.startswith(REJECTED)
    assert "1. citation c1" in result
    assert ctx.accepted is None
    assert ctx.rejections == 1
