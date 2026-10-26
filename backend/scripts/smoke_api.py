"""§94 全链路 API 冒烟：登录→项目→需求→用例→计划→Run→P/F→缺陷→回归→报告。

用法（先启动 dev server：python manage.py runserver 8000）：
    python scripts/smoke_api.py [http://127.0.0.1:8000]

输出每步耗时与断言结果，最后打印耗时统计（供 P95 量化）。
"""
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"

results = []
tokens = []


class ApiClient:
    def __init__(self):
        self.token = None

    def request(self, method, path, payload=None, expect_code=0):
        url = f"{API}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode())
        elapsed = (time.perf_counter() - started) * 1000
        results.append((method, path, elapsed, body.get("code")))
        if expect_code is not None and body.get("code") != expect_code:
            raise AssertionError(f"{method} {path} 期望 code={expect_code} 实得 {body} ")
        return body


def step(name):
    print(f"[smoke] {name}")


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import django

    django.setup()
    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = f"smoke_{uuid.uuid4().hex[:8]}@nanoqa.local"
    user = User.objects.create_user(
        username=email, email=email, password="Smoke#12345", display_name="冒烟用户", is_system_admin=True
    )

    cli = ApiClient()
    step("1. 登录")
    body = cli.request("POST", "/auth/login/", {"email": email, "password": "Smoke#12345"})
    cli.token = body["data"]["access"]

    step("2. 创建组织与项目")
    org = cli.request("POST", "/organizations/", {"name": "冒烟组织", "slug": f"smoke-{uuid.uuid4().hex[:6]}"})["data"]
    project = cli.request("POST", "/projects/", {
        "organization_id": org["id"], "name": "电商 App", "key": f"SM{uuid.uuid4().hex[:4].upper()}",
    })["data"]
    pid = project["id"]

    step("3. 模块树")
    module = cli.request("POST", f"/projects/{pid}/modules/", {"name": "用户中心", "parent_id": None})["data"]
    cli.request("GET", f"/projects/{pid}/modules/")

    step("4. 需求")
    requirement = cli.request("POST", f"/projects/{pid}/requirements/", {
        "title": "新增微信支付", "description": "支持微信支付下单与退款",
    })["data"]

    step("5. 用例（编号 + 版本）")
    case_payload = {
        "title": "微信支付-正常支付", "module_id": module["id"], "priority": "P0",
        "precondition": "用户已登录",
        "steps": [
            {"action": "打开收银台", "expected": "显示支付方式"},
            {"action": "选择微信支付并确认", "expected": "支付成功，订单状态变为已支付"},
        ],
    }
    case = cli.request("POST", f"/projects/{pid}/testcases/", case_payload)["data"]
    assert case["case_key"].endswith("TC-000001"), case["case_key"]
    cli.request("POST", f"/requirements/{requirement['id']}/testcases/", {"test_case_ids": [case["id"]]})
    cli.request("GET", f"/testcases/{case['id']}/versions/")

    step("6. 更新用例 → 版本递增（乐观锁）")
    updated = cli.request("PATCH", f"/testcases/{case['id']}/", {
        "updated_at": case["updated_at"], "title": "微信支付-正常支付（修订）",
    })["data"]
    assert updated["current_version"] == 2, updated["current_version"]

    step("7. 测试计划 + 加入用例 + 开始执行")
    plan = cli.request("POST", f"/projects/{pid}/testplans/", {
        "name": "v1.0 回归", "version": "1.0",
    })["data"]
    cli.request("POST", f"/testplans/{plan['id']}/cases/", {"test_case_ids": [case["id"]]})
    run = cli.request("POST", f"/testplans/{plan['id']}/start/", {"environment": "Staging", "build_version": "1.0.0"})["data"]

    step("8. 执行 PASS / FAIL")
    results_page = cli.request("GET", f"/runs/{run['id']}/results/")["data"]
    result_id = results_page["items"][0]["id"]
    cli.request("POST", f"/runs/{run['id']}/results/", {
        "test_case_id": case["id"], "status": "failed", "actual_result": "支付接口返回 500", "duration": 12,
    })

    step("9. FAIL 创建缺陷并关联")
    defect = cli.request("POST", f"/results/{result_id}/defects/", {
        "title": "支付接口返回500", "severity": "Major", "priority": "P1",
    })["data"]["defect"]
    assert defect["key"].endswith("BUG-000001"), defect["key"]

    step("10. 开发修复 → 缺陷流转 → 回归 PASS")
    cli.request("PATCH", f"/defects/{defect['id']}/", {"updated_at": defect["updated_at"], "status": "In Progress"})
    defect2 = cli.request("GET", f"/defects/{defect['id']}/")["data"]
    cli.request("PATCH", f"/defects/{defect['id']}/", {"updated_at": defect2["updated_at"], "status": "Resolved"})
    cli.request("POST", f"/runs/{run['id']}/results/", {
        "test_case_id": case["id"], "status": "passed", "actual_result": "支付成功", "duration": 8,
    })

    step("11. 报告 / Dashboard / 覆盖率")
    report = cli.request("GET", f"/runs/{run['id']}/report/")["data"]
    dashboard = cli.request("GET", f"/projects/{pid}/dashboard/")["data"]
    coverage = cli.request("GET", f"/requirements/{requirement['id']}/coverage/")["data"]
    assert report["overview"]["pass_rate"] == 100.0 or report["overview"]["pass_rate"] == 1.0, report["overview"]

    step("12. AI 生成（Mock）→ 人工审核入库")
    ai = cli.request("POST", "/ai/testcases/generate/", {"requirement_id": requirement["id"], "count": 3})["data"]
    accepted = cli.request("POST", f"/ai/tasks/{ai['task_id']}/accept/", {})["data"]

    step("13. 审计日志")
    cli.request("GET", f"/projects/{pid}/audit-logs/")

    # 统计
    latencies = [r[2] for r in results]
    p95 = statistics.quantiles(latencies, n=20)[-1] if len(latencies) >= 5 else max(latencies)
    print("\n=== 冒烟通过 ===")
    print(f"请求总数: {len(results)}  平均: {statistics.mean(latencies):.1f}ms  P95: {p95:.1f}ms  最大: {max(latencies):.1f}ms")
    print(f"用例编号: {case['case_key']}  缺陷: {defect['key']}  AI 入库: {len(accepted.get('test_cases', accepted) if isinstance(accepted, dict) else accepted)} 条")
    for method, path, elapsed, code in results:
        print(f"  {method:6s} {path:52s} {elapsed:7.1f}ms code={code}")


if __name__ == "__main__":
    main()
