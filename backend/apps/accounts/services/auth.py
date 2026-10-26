"""认证服务：登录 / 登出 / me（§45 Auth）。"""
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from common.exceptions import NanoAPIError


def login(email: str, password: str) -> tuple[User, dict]:
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise NanoAPIError("邮箱或密码错误")
    if not user.is_active:
        raise NanoAPIError("账号已停用")
    user = authenticate(username=user.username, password=password)
    if user is None:
        raise NanoAPIError("邮箱或密码错误")
    refresh = RefreshToken.for_user(user)
    return user, {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def logout(refresh_token: str):
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception:
        raise NanoAPIError("无效的刷新令牌")
