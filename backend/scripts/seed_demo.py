"""开发演示数据种子（幂等）：稳定账号 + SHOP 项目示例数据。

用法：python scripts/seed_demo.py
账号：admin@nanoqa.dev / Admin#12345（系统管理员）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.defects.models import Defect, TestCaseDefect, TestResultDefect  # noqa: E402
from apps.executions.models import TestResult, TestRun  # noqa: E402
from apps.organizations.models import Organization  # noqa: E402
from apps.projects.models import Module, NumberSequence, Project  # noqa: E402
from apps.requirements.models import Requirement, RequirementTestCase  # noqa: E402
from apps.testcases.models import TestCase, TestCaseVersion  # noqa: E402
from apps.testplans.models import TestPlan, TestPlanCase  # noqa: E402


def steps(*pairs):
    return [{"order": i + 1, "action": a, "expected": e} for i, (a, e) in enumerate(pairs)]


@transaction.atomic
def main():
    user, _ = User.objects.update_or_create(
        email="admin@nanoqa.dev",
        defaults={
            "username": "admin",
            "display_name": "系统管理员",
            "is_system_admin": True,
            "is_superuser": True,
            "is_staff": True,
        },
    )
    user.set_password("Admin#12345")
    user.save()

    org, _ = Organization.objects.update_or_create(
        slug="shop-org", defaults={"name": "Shop 演示组织", "owner": user}
    )

    project, created = Project.objects.update_or_create(
        key="SHOP",
        defaults={"name": "SHOP 电商平台", "organization": org, "owner": user, "description": "演示项目"},
    )

    def module(name, parent=None):
        obj, _ = Module.objects.get_or_create(project=project, name=name, parent=parent)
        return obj

    m_order = module("订单")
    m_pay = module("支付")
    m_user = module("用户")

    def case(case_key, title, mod, priority="P1", case_type="functional", status="active", st=()):
        obj, _ = TestCase.objects.update_or_create(
            project=project,
            case_key=case_key,
            defaults={
                "organization": org,
                "title": title,
                "module": mod,
                "priority": priority,
                "case_type": case_type,
                "status": status,
                "precondition": "用户已登录",
                "creator": user,
                "owner": user,
                "current_version": 1,
            },
        )
        TestCaseVersion.objects.get_or_create(
            test_case=obj,
            version=1,
            defaults={
                "title": title,
                "precondition": "用户已登录",
                "steps": steps(*st),
                "change_summary": "初始版本",
                "created_by": user,
            },
        )
        return obj

    c1 = case("SHOP-TC-000001", "下单成功生成待支付订单", m_order, "P0", st=(
        ("进入商品详情页点击立即购买", "进入确认订单页"),
        ("选择收货地址并提交订单", "订单创建成功，状态为待支付"),
    ))
    c2 = case("SHOP-TC-000002", "未选地址时下单提示缺少收货地址", m_order, "P1", st=(
        ("不选择收货地址直接提交订单", "提示请选择收货地址"),
    ))
    c3 = case("SHOP-TC-000003", "支付宝支付成功回调更新订单状态", m_pay, "P0", st=(
        ("发起支付宝支付并完成付款", "支付回调返回 success，订单状态更新为已支付"),
    ))
    c4 = case("SHOP-TC-000004", "支付超时订单自动关闭", m_pay, "P1", "functional", st=(
        ("创建订单后 30 分钟不支付", "订单自动关闭并释放库存"),
    ))
    c5 = case("SHOP-TC-000005", "手机号注册并校验验证码", m_user, "P1", st=(
        ("输入手机号获取验证码并注册", "注册成功并自动登录"),
    ))
    case("SHOP-TC-000006", "密码错误 5 次锁定账号", m_user, "P2", "security", "draft", st=(
        ("连续 5 次输入错误密码登录", "账号锁定 30 分钟"),
    ))

    req, _ = Requirement.objects.update_or_create(
        project=project,
        key="SHOP-REQ-0001",
        defaults={
            "organization": org,
            "title": "下单与支付主流程",
            "description": "支持用户完成下单、支付，超时自动关单。",
            "status": "approved",
            "creator": user,
            "owner": user,
        },
    )
    for c in (c1, c2, c3):
        RequirementTestCase.objects.get_or_create(requirement=req, test_case=c)

    plan, _ = TestPlan.objects.update_or_create(
        project=project,
        name="v1.0 回归测试",
        defaults={
            "organization": org,
            "version": "1.0",
            "status": "in_progress",
            "owner": user,
            "created_by": user,
        },
    )
    for c in (c1, c2, c3, c4):
        TestPlanCase.objects.get_or_create(
            test_plan=plan, test_case=c, defaults={"assigned_to": user}
        )

    run, run_created = TestRun.objects.get_or_create(
        test_plan=plan,
        name="v1.0 回归 - 第 1 轮",
        defaults={
            "organization": org,
            "project": project,
            "environment": "Staging",
            "build_version": "1.0.0",
            "status": "running",
            "created_by": user,
        },
    )
    if run_created:
        for c in (c1, c2, c3, c4):
            version = c.versions.get(version=c.current_version)
            status = {"SHOP-TC-000001": "passed", "SHOP-TC-000002": "passed",
                      "SHOP-TC-000003": "failed", "SHOP-TC-000004": "not_run"}[c.case_key]
            TestResult.objects.create(
                test_run=run,
                test_case=c,
                test_case_version=version,
                status=status,
                executed_by=user if status != "not_run" else None,
                actual_result="符合预期" if status == "passed" else ("支付回调 500" if status == "failed" else ""),
                duration=8 if status != "not_run" else 0,
            )
        failed_result = TestResult.objects.get(test_run=run, test_case=c3)
        defect, _ = Defect.objects.update_or_create(
            project=project,
            key="SHOP-BUG-000001",
            defaults={
                "organization": org,
                "title": "支付宝支付回调返回 500",
                "description": "支付回调接口异常，订单状态未更新。",
                "severity": "Critical",
                "priority": "P0",
                "status": "Open",
                "environment": "Staging",
                "version": "1.0.0",
                "reporter": user,
            },
        )
        TestCaseDefect.objects.get_or_create(test_case=c3, defect=defect)
        TestResultDefect.objects.get_or_create(test_result=failed_result, defect=defect)

    # 种子直插的编号需推进取号序列，否则 next_key 与已有编号冲突
    for entity, nxt in (("TC", 7), ("BUG", 2), ("REQ", 2)):
        NumberSequence.objects.update_or_create(
            project=project, entity=entity, defaults={"next_value": nxt}
        )

    print("种子数据就绪：admin@nanoqa.dev / Admin#12345，项目 SHOP（用例 6 / 需求 1 / 计划 1 / Run 1 / 缺陷 1）")


if __name__ == "__main__":
    main()
