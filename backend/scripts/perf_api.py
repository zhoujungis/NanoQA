"""§72 性能核验：量化实测关键接口延迟。

目标：用例列表 < 500ms（1000 用例）、Dashboard < 1s、单接口 P95 < 300ms。

用法：先启动后端 dev server（python manage.py runserver 8000），再执行
  python scripts/perf_api.py
脚本会在开发库中确保存在 PERF 项目（1000 条用例，幂等），仅作测量夹具。
"""
import math
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.organizations.models import Organization  # noqa: E402
from apps.projects.models import Project  # noqa: E402
from apps.testcases.models import TestCase  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"
N = 30  # 每个接口测量次数
PERF_CASES = 1000


def ensure_fixture():
    """幂等准备 PERF 项目 + 1000 条用例（不含版本，纯列表测量夹具）。"""
    admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_system_admin=True).first()
    org, _ = Organization.objects.get_or_create(slug="perf-org", defaults={"name": "性能测量组织", "owner": admin})
    project, _ = Project.objects.get_or_create(
        key="PERF", defaults={"name": "性能测量项目", "organization": org, "owner": admin}
    )
    existing = TestCase.objects.filter(project=project).count()
    if existing < PERF_CASES:
        batch = [
            TestCase(
                organization=org,
                project=project,
                case_key=f"PERF-TC-{i:06d}",
                title=f"性能测量用例 {i:06d}：下单流程校验",
                priority=["P0", "P1", "P2", "P3"][i % 4],
                case_type="functional",
                status="active",
                creator=admin,
                owner=admin,
                current_version=1,
            )
            for i in range(existing, PERF_CASES)
        ]
        with transaction.atomic():
            TestCase.objects.bulk_create(batch, batch_size=500)
    return project


def http(path, token=None):
    # 路径含中文查询值（q=下单），需 URL 编码，否则 urllib 按 ASCII 发送报错
    req = urllib.request.Request(f"{API}{urllib.parse.quote(path, safe='/?&=%.')}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


def login():
    import json

    payload = json.dumps({"email": "admin@nanoqa.dev", "password": "Admin#12345"}).encode()
    req = urllib.request.Request(f"{API}/auth/login/", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    return body["data"]["access"]


def measure(path, token, label, budget_ms):
    times = []
    for _ in range(N):
        start = time.perf_counter()
        status, _ = http(path, token)
        elapsed = (time.perf_counter() - start) * 1000
        assert status == 200, f"{path} -> HTTP {status}"
        times.append(elapsed)
    times.sort()
    avg = sum(times) / len(times)
    p95 = times[math.ceil(0.95 * len(times)) - 1]
    print(f"{label:<28} 平均 {avg:7.1f}ms  P50 {times[len(times)//2]:7.1f}ms  P95 {p95:7.1f}ms  最大 {times[-1]:7.1f}ms  预算 <{budget_ms}ms  {'通过' if p95 < budget_ms else '未达标'}")
    return {"label": label, "avg": round(avg, 1), "p95": round(p95, 1), "max": round(times[-1], 1), "budget": budget_ms, "pass": p95 < budget_ms}


def main():
    project = ensure_fixture()
    token = login()
    pid = project.id

    # 取 SHOP 的 run 用于报告测量
    import json

    _, raw = http(f"/projects/", token)
    shop_runs = None
    for item in json.loads(raw)["data"]["items"]:
        if item["key"] == "SHOP":
            _, runs_raw = http(f"/projects/{item['id']}/reports/", token)
            items = json.loads(runs_raw)["data"]["items"]
            if items:
                shop_runs = items[0]["run_id"]
            break

    print(f"=== §72 性能核验（{N} 次/接口，{PERF_CASES} 用例夹具，目标 P95<300ms） ===")
    results = [
        measure(f"/projects/{pid}/testcases/?page=1&page_size=20", token, "用例列表 1000 条", 500),
        measure(f"/projects/{pid}/testcases/?q=下单&page=1&page_size=20", token, "用例搜索 q=下单", 500),
        measure(f"/projects/{pid}/dashboard/", token, "项目 Dashboard", 1000),
    ]
    if shop_runs:
        results.append(measure(f"/runs/{shop_runs}/report/", token, "Run 报告", 1000))
    results.append(measure(f"/projects/{pid}/defects/?page=1&page_size=20", token, "缺陷列表", 500))

    failed = [r for r in results if not r["pass"]]
    print(f"=== 结论：{len(results) - len(failed)}/{len(results)} 项达标 ===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
