from unittest.mock import patch

from backend.app.services.radar import _crawl_lock, _crawl_log, CrawlLogEntry


def test_post_radar_run_returns_started(client):
    with patch("backend.app.routers.radar._run_crawl_bg"), \
         patch.object(_crawl_lock, "locked", return_value=False):
        response = client.post("/radar/run")
    assert response.status_code == 200
    assert response.json() == {"started": True}


def test_post_radar_run_409_when_busy(client):
    with patch.object(_crawl_lock, "locked", return_value=True):
        response = client.post("/radar/run")
    assert response.status_code == 409


def test_get_radar_log_empty(client):
    _crawl_log.clear()
    response = client.get("/radar/log")
    assert response.status_code == 200
    assert response.json() == []


def test_get_radar_log_with_entries(client):
    _crawl_log.clear()
    entry = CrawlLogEntry(
        company_id="abc",
        company_name="Wix",
        run_at="2026-03-17T10:00:00",
        status="success",
        new_postings=3,
        error_message=None,
    )
    _crawl_log.append(entry)
    response = client.get("/radar/log")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["company_name"] == "Wix"
    _crawl_log.clear()


def test_get_radar_log_reverses_chronological_order(client):
    _crawl_log.clear()
    older = CrawlLogEntry(
        company_id="1",
        company_name="OldCo",
        run_at="2026-03-17T08:00:00",
        status="success",
        new_postings=1,
        error_message=None,
    )
    newer = CrawlLogEntry(
        company_id="2",
        company_name="NewCo",
        run_at="2026-03-17T10:00:00",
        status="success",
        new_postings=2,
        error_message=None,
    )
    _crawl_log.append(older)
    _crawl_log.append(newer)
    response = client.get("/radar/log")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["company_name"] == "NewCo"
    assert data[1]["company_name"] == "OldCo"
    _crawl_log.clear()
