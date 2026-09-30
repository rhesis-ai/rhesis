from docs_assistant.corpus.changelog import select_entries


def test_changelog_versions_are_parsed_with_dates_and_anchors(snapshot):
    entries = snapshot.changelog
    assert entries[0].version == "Unreleased"
    released = entries[1:]
    assert len(released) == 3
    assert released[0].date and released[0].date.count("-") == 2
    page = snapshot.page("changelog")
    assert all(e.anchor in page.anchors for e in entries)
    # Subsections such as "### Added" are folded into their version.
    assert "###" in released[0].body


def test_default_selection_is_latest_releases_first(snapshot):
    selected = select_entries(snapshot.changelog)
    assert selected[0].version == snapshot.changelog[1].version
    assert all(e.version != "Unreleased" for e in selected)


def test_version_since_and_query_filters(snapshot):
    newest, middle, oldest = snapshot.changelog[1:4]
    assert [e.version for e in select_entries(snapshot.changelog, version=middle.version)] == [
        middle.version
    ]
    assert [
        e.version for e in select_entries(snapshot.changelog, version=f"v{oldest.version}")
    ] == [oldest.version]
    since = select_entries(snapshot.changelog, since=oldest.version)
    assert [e.version for e in since] == [newest.version, middle.version]
    assert select_entries(snapshot.changelog, query="zzqqxx") == []
    # Filler words don't filter anything; real terms do.
    assert len(select_entries(snapshot.changelog, query="what's new")) == 3
    kubernetes = select_entries(snapshot.changelog, query="Kubernetes")
    assert kubernetes and all("kubernetes" in e.body.lower() for e in kubernetes)
