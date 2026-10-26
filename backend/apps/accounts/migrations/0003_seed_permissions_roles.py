"""种子数据：权限与系统角色（§4）。"""
from django.db import migrations

PERMISSIONS = [
    ("project.read", "查看项目", "project"), ("project.create", "创建项目", "project"),
    ("project.update", "修改项目", "project"), ("project.delete", "删除项目", "project"),
    ("requirement.read", "查看需求", "requirement"), ("requirement.create", "创建需求", "requirement"),
    ("requirement.update", "修改需求", "requirement"), ("requirement.delete", "删除需求", "requirement"),
    ("testcase.read", "查看用例", "testcase"), ("testcase.create", "创建用例", "testcase"),
    ("testcase.update", "修改用例", "testcase"), ("testcase.delete", "删除用例", "testcase"),
    ("testcase.execute", "执行用例", "testcase"), ("testcase.review", "评审用例", "testcase"),
    ("testplan.read", "查看计划", "testplan"), ("testplan.create", "创建计划", "testplan"),
    ("testplan.update", "修改计划", "testplan"), ("testplan.delete", "删除计划", "testplan"),
    ("testplan.execute", "执行计划", "testplan"),
    ("defect.read", "查看缺陷", "defect"), ("defect.create", "创建缺陷", "defect"),
    ("defect.update", "修改缺陷", "defect"), ("defect.delete", "删除缺陷", "defect"),
    ("report.read", "查看报告", "report"),
    ("user.manage", "用户管理", "system"), ("role.manage", "角色管理", "system"),
    ("audit.read", "查看审计日志", "system"),
]

ROLE_PERMISSIONS = {
    "admin": ("管理员", [p[0] for p in PERMISSIONS]),
    "pm": ("项目负责人", [
        "project.read", "project.update",
        "requirement.read", "requirement.create", "requirement.update",
        "testcase.read", "testcase.create", "testcase.update", "testcase.review",
        "testplan.read", "testplan.create", "testplan.update", "testplan.delete", "testplan.execute",
        "defect.read", "defect.create", "defect.update",
        "report.read", "user.manage", "audit.read",
    ]),
    "qa": ("测试工程师", [
        "project.read",
        "requirement.read", "requirement.create", "requirement.update",
        "testcase.read", "testcase.create", "testcase.update", "testcase.delete",
        "testcase.execute", "testcase.review",
        "testplan.read", "testplan.create", "testplan.update", "testplan.execute",
        "defect.read", "defect.create", "defect.update",
        "report.read",
    ]),
    "dev": ("开发人员", [
        "project.read", "requirement.read", "testcase.read",
        "defect.read", "defect.update", "report.read",
    ]),
    "viewer": ("只读用户", [
        "project.read", "requirement.read", "testcase.read",
        "testplan.read", "defect.read", "report.read",
    ]),
}


def seed(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    for codename, name, group in PERMISSIONS:
        Permission.objects.get_or_create(codename=codename, defaults={"name": name, "group": group})

    for code, (name, codenames) in ROLE_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(code=code, defaults={"name": name, "is_system": True})
        for codename in codenames:
            permission = Permission.objects.get(codename=codename)
            RolePermission.objects.get_or_create(role=role, permission=permission)


def unseed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code__in=list(ROLE_PERMISSIONS)).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
