"""统一响应渲染：{code, message, data}（§44）。"""
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer

ENVELOPE_KEY = "__nano_envelope__"


def envelope(code: int, message: str, data):
    """构造已封装响应体；渲染器识别后原样输出。"""
    return {ENVELOPE_KEY: True, "code": code, "message": message, "data": data}


class NanoJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, dict) and data.get(ENVELOPE_KEY):
            payload = {"code": data["code"], "message": data["message"], "data": data["data"]}
        else:
            payload = {"code": 0, "message": "success", "data": data}
        return super().render(payload, accepted_media_type, renderer_context)


class NanoBrowsableAPIRenderer(BrowsableAPIRenderer):
    """保留 DRF 调试页，但默认不参与 JSON 客户端协商。"""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, dict) and data.get(ENVELOPE_KEY):
            data = {"code": data["code"], "message": data["message"], "data": data["data"]}
        return super().render(data, accepted_media_type, renderer_context)
