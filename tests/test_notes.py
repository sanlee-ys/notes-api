from fastapi import status


def _create(client, title="Test Note", content="Test content", tags=None):
    payload = {"title": title, "content": content, "tags": tags or []}
    resp = client.post("/notes", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


# --- CREATE ---


class TestCreate:
    def test_returns_201_with_fields(self, client):
        resp = client.post("/notes", json={"title": "My Note", "content": "Hello"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "My Note"
        assert body["content"] == "Hello"
        assert body["tags"] == []
        assert body["enrichment_status"] == "pending"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_with_tags(self, client):
        note = _create(client, tags=["cyber", "policy"])
        assert set(note["tags"]) == {"cyber", "policy"}

    def test_missing_title_422(self, client):
        resp = client.post("/notes", json={"content": "ok"})
        assert resp.status_code == 422

    def test_empty_title_422(self, client):
        resp = client.post("/notes", json={"title": "", "content": "ok"})
        assert resp.status_code == 422

    def test_missing_content_422(self, client):
        resp = client.post("/notes", json={"title": "ok"})
        assert resp.status_code == 422

    def test_title_too_long_422(self, client):
        resp = client.post("/notes", json={"title": "x" * 256, "content": "ok"})
        assert resp.status_code == 422

    def test_content_too_long_422(self, client):
        resp = client.post("/notes", json={"title": "ok", "content": "x" * 10001})
        assert resp.status_code == 422

    def test_tag_too_long_422(self, client):
        resp = client.post(
            "/notes", json={"title": "ok", "content": "ok", "tags": ["x" * 51]}
        )
        assert resp.status_code == 422

    def test_too_many_tags_422(self, client):
        resp = client.post(
            "/notes",
            json={"title": "ok", "content": "ok", "tags": [str(i) for i in range(21)]},
        )
        assert resp.status_code == 422


# --- GET ---


class TestGet:
    def test_list_empty(self, client):
        assert client.get("/notes").json() == []

    def test_list_returns_all(self, client):
        _create(client, title="A")
        _create(client, title="B")
        assert len(client.get("/notes").json()) == 2

    def test_get_by_id(self, client):
        note = _create(client)
        resp = client.get(f"/notes/{note['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == note["id"]

    def test_get_nonexistent_404(self, client):
        assert client.get("/notes/9999").status_code == 404


# --- SEARCH ---


class TestSearch:
    def test_q_matches_title(self, client):
        _create(client, title="Defense procurement contract")
        _create(client, title="Space operations update")
        results = client.get("/notes?q=procurement").json()
        assert len(results) == 1
        assert results[0]["title"] == "Defense procurement contract"

    def test_q_matches_content(self, client):
        _create(client, content="Article about cyber warfare")
        _create(client, content="Land operations briefing")
        assert len(client.get("/notes?q=cyber").json()) == 1

    def test_q_case_insensitive(self, client):
        _create(client, title="CYBER security update")
        assert len(client.get("/notes?q=cyber").json()) == 1

    def test_tag_filter(self, client):
        _create(client, title="Note 1", tags=["cyber"])
        _create(client, title="Note 2", tags=["policy"])
        results = client.get("/notes?tag=cyber").json()
        assert len(results) == 1
        assert results[0]["title"] == "Note 1"

    def test_no_results(self, client):
        _create(client, title="Some note")
        assert client.get("/notes?q=xyz_nonexistent").json() == []


# --- PUBLISHED_AT ---


class TestPublishedAt:
    def test_defaults_to_null(self, client):
        note = _create(client)
        assert note["published_at"] is None

    def test_round_trips_on_create(self, client):
        resp = client.post(
            "/notes",
            json={
                "title": "F-35 award",
                "content": "Contract signed.",
                "published_at": "2014-03-15T00:00:00",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["published_at"] == "2014-03-15T00:00:00"

    def test_accepts_date_only_string(self, client):
        resp = client.post(
            "/notes",
            json={"title": "t", "content": "c", "published_at": "2014-03-15"},
        )
        assert resp.status_code == 201
        assert resp.json()["published_at"].startswith("2014-03-15")

    def test_update_sets_published_at(self, client):
        note = _create(client)
        resp = client.put(
            f"/notes/{note['id']}",
            json={"title": "T", "content": "C", "published_at": "2020-01-01T00:00:00"},
        )
        assert resp.json()["published_at"] == "2020-01-01T00:00:00"


class TestPublishedAtFilter:
    def _seed_dated(self, client, title, date):
        client.post(
            "/notes", json={"title": title, "content": "c", "published_at": date}
        )

    def test_filters_to_a_year_range(self, client):
        self._seed_dated(client, "Old", "2013-12-31")
        self._seed_dated(client, "InRange", "2014-06-01")
        self._seed_dated(client, "New", "2015-01-01")
        results = client.get(
            "/notes?published_after=2014-01-01&published_before=2014-12-31"
        ).json()
        titles = {r["title"] for r in results}
        assert titles == {"InRange"}

    def test_undated_notes_excluded_from_range(self, client):
        _create(client, title="Undated")  # no published_at
        self._seed_dated(client, "Dated", "2014-06-01")
        results = client.get("/notes?published_after=2014-01-01").json()
        assert {r["title"] for r in results} == {"Dated"}

    def test_range_composes_with_tag(self, client):
        client.post(
            "/notes",
            json={
                "title": "Tagged2014",
                "content": "c",
                "tags": ["cyber"],
                "published_at": "2014-06-01",
            },
        )
        self._seed_dated(client, "Untagged2014", "2014-07-01")
        results = client.get("/notes?tag=cyber&published_after=2014-01-01").json()
        assert {r["title"] for r in results} == {"Tagged2014"}


# --- UPDATE ---


class TestUpdate:
    def test_update_200(self, client):
        note = _create(client)
        resp = client.put(
            f"/notes/{note['id']}", json={"title": "Updated", "content": "New"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_nonexistent_404(self, client):
        resp = client.put("/notes/9999", json={"title": "x", "content": "y"})
        assert resp.status_code == 404

    def test_update_replaces_tags(self, client):
        note = _create(client, tags=["old"])
        resp = client.put(
            f"/notes/{note['id']}", json={"title": "T", "content": "C", "tags": ["new"]}
        )
        assert resp.json()["tags"] == ["new"]


# --- SET TAGS ---


class TestSetTags:
    def test_set_tags_200(self, client):
        note = _create(client)
        resp = client.put(f"/notes/{note['id']}/tags", json={"tags": ["cyber", "land"]})
        assert resp.status_code == 200
        assert set(resp.json()["tags"]) == {"cyber", "land"}

    def test_set_tags_nonexistent_404(self, client):
        assert (
            client.put("/notes/9999/tags", json={"tags": ["cyber"]}).status_code == 404
        )

    def test_clear_tags(self, client):
        note = _create(client, tags=["old"])
        resp = client.put(f"/notes/{note['id']}/tags", json={"tags": []})
        assert resp.json()["tags"] == []


# --- DELETE ---


class TestDelete:
    def test_delete_204(self, client):
        note = _create(client)
        assert client.delete(f"/notes/{note['id']}").status_code == 204

    def test_delete_makes_note_gone(self, client):
        note = _create(client)
        client.delete(f"/notes/{note['id']}")
        assert client.get(f"/notes/{note['id']}").status_code == 404

    def test_delete_nonexistent_404(self, client):
        assert client.delete("/notes/9999").status_code == 404
