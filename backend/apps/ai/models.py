"""AI 任务（§38）：AI 输出只进 Draft，人工审核后才入库（坑 3）。"""
from django.conf import settings
from django.db import models


class AITask(models.Model):
    TASK_TYPES = [
        ("generate_testcases", "生成用例"),
        ("review_testcase", "评审用例"),
        ("expand_edge_cases", "补充边界场景"),
        ("detect_duplicate_cases", "重复用例检测"),
        ("analyze_requirement", "需求分析"),
        ("analyze_defect", "缺陷分析"),
        ("generate_test_data", "生成测试数据"),
        ("analyze_test_report", "测试报告分析"),
    ]
    STATUS_QUEUED, STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED = "queued", "running", "succeeded", "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "排队中"), (STATUS_RUNNING, "执行中"),
        (STATUS_SUCCEEDED, "成功"), (STATUS_FAILED, "失败"),
    ]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="ai_tasks")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="ai_tasks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_tasks")
    task_type = models.CharField(max_length=32, choices=TASK_TYPES)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    model = models.CharField(max_length=64, blank=True, default="mock")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    tokens = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_aitask"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "task_type"])]
