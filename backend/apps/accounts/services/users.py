"""用户查询服务（用户管理列表）。"""
from django.db.models import Q

from apps.accounts.models import User


def search_users(q: str | None = None):
    """用户列表，支持用户名 / 邮箱 / 显示名模糊搜索。"""
    queryset = User.objects.all().order_by("id")
    if q:
        queryset = queryset.filter(
            Q(username__icontains=q) | Q(email__icontains=q) | Q(display_name__icontains=q)
        )
    return queryset
