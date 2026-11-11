"""破坏性路由的 CSRF 校验：无令牌 400，带令牌放行，非破坏性路由不受影响。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from experiment_report_grader.app import CSRF_TOKEN, app


def test_destructive_post_requires_token():
    client = app.test_client()
    was_testing = app.testing
    app.testing = False
    try:
        resp = client.post("/pilot/delete", json={"filename": "不存在的样本.docx"})
        assert resp.status_code == 400, resp.status_code
        assert "令牌" in resp.get_json()["error"], resp.get_json()

        resp = client.post("/pilot/delete", json={"filename": "不存在的样本.docx"},
                           headers={"X-CSRF-Token": CSRF_TOKEN})
        assert resp.status_code == 404, "带令牌应走到业务逻辑而不是被拦"

        resp = client.post("/session/switch", data={"session_id": "不存在的课程"})
        assert resp.status_code == 404, "非破坏性路由不校验令牌"
    finally:
        app.testing = was_testing


def test_spa_shell_injects_token():
    html = app.test_client().get("/app").get_data(as_text=True)
    assert f'<meta name="csrf-token" content="{CSRF_TOKEN}">' in html
