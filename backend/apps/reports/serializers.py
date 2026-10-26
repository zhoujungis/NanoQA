"""报告序列化器：聚合结果以 Service 产出 dict 为准，此处只做 run 报告列表行渲染。"""
from rest_framework import serializers


class RunReportSummarySerializer(serializers.Serializer):
    run_id = serializers.IntegerField(source="id")
    name = serializers.CharField()
    status = serializers.CharField()
    environment = serializers.CharField()
    build_version = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    total = serializers.IntegerField()
    passed = serializers.IntegerField()
    failed = serializers.IntegerField()
    not_run = serializers.IntegerField()
    pass_rate = serializers.SerializerMethodField()

    def get_pass_rate(self, obj) -> float:
        executed = (obj.total or 0) - (obj.not_run or 0)
        return round(obj.passed / executed, 4) if executed else 0.0
