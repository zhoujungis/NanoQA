"""编号生成：select_for_update 取号，单调递增、永不复用（§49）。"""
from django.db import transaction

from apps.projects.models import NumberSequence, Project
from common.utils import format_key


def next_key(project: Project, entity: str, width: int = 6) -> str:
    """生成下一个业务编号，如 SHOP-TC-000001。必须在调用方事务内使用。"""
    if entity not in {c[0] for c in NumberSequence.ENTITY_CHOICES}:
        raise ValueError(f"unknown entity: {entity}")
    with transaction.atomic():
        seq, _created = (
            NumberSequence.objects.select_for_update()
            .get_or_create(project=project, entity=entity, defaults={"next_value": 1})
        )
        value = seq.next_value
        seq.next_value = value + 1
        seq.save(update_fields=["next_value"])
    return format_key(project.key, entity, value, width=width)
