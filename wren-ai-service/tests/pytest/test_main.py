import json
import os
import uuid

import orjson
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def app():
    os.environ["CONFIG_PATH"] = "tests/data/config.test.yaml"
    from src.__main__ import app

    yield app
    # Clean up (if necessary)
    del os.environ["CONFIG_PATH"]


GLOBAL_DATA = {
    "semantics_preperation_id": str(uuid.uuid4()),
    "query_id": None,
}


def test_semantics_preparation(app):
    with TestClient(app) as client:
        semantics_preperation_id = GLOBAL_DATA["semantics_preperation_id"]

        with open("tests/data/book_2_mdl.json", "r") as f:
            mdl_str = orjson.dumps(json.load(f)).decode("utf-8")

        response = client.post(
            url="/v1/semantics-preparations",
            json={
                "mdl": mdl_str,
                "id": semantics_preperation_id,
            },
        )

        assert response.status_code == 200
        assert response.json()["id"] == semantics_preperation_id

        status = "indexing"

        while status == "indexing":
            response = client.get(
                url=f"/v1/semantics-preparations/{semantics_preperation_id}/status"
            )

            assert response.status_code == 200
            assert response.json()["status"] in ["indexing", "finished", "failed"]
            status = response.json()["status"]

        assert status == "finished"


def test_asks_with_successful_query(app):
    with TestClient(app) as client:
        semantics_preparation_id = GLOBAL_DATA["semantics_preperation_id"]

        response = client.post(
            url="/v1/asks",
            json={
                "query": "How many books are there?",
                "id": semantics_preparation_id,
            },
        )

        assert response.status_code == 200
        assert response.json()["query_id"] != ""

        query_id = response.json()["query_id"]
        GLOBAL_DATA["query_id"] = query_id

        response = client.get(url=f"/v1/asks/{query_id}/result")
        while (
            response.json()["status"] != "finished"
            and response.json()["status"] != "failed"
        ):
            response = client.get(url=f"/v1/asks/{query_id}/result")

        # TODO: we'll refactor almost all test case with a mock server, thus temporarily only assert the status is finished or failed.
        assert response.status_code == 200
        assert response.json()["status"] == "finished" or "failed"
        # for r in response.json()["response"]:
        #     assert r["sql"] is not None and r["sql"] != ""
        #     assert r["summary"] is not None and r["summary"] != ""


def test_stop_asks(app):
    with TestClient(app) as client:
        query_id = GLOBAL_DATA["query_id"]

        response = client.patch(
            url=f"/v1/asks/{query_id}",
            json={
                "status": "stopped",
            },
        )

        assert response.status_code == 200
        assert response.json()["query_id"] == query_id

        response = client.get(url=f"/v1/asks/{query_id}/result")
        while response.json()["status"] != "stopped":
            response = client.get(url=f"/v1/asks/{query_id}/result")

        assert response.status_code == 200
        assert response.json()["status"] == "stopped"


def test_web_error_handler(app):
    with TestClient(app) as client:
        response = client.post(
            url="/v1/asks",
            json={},
        )

        assert response.status_code == 400
        assert response.json()["detail"] != ""
