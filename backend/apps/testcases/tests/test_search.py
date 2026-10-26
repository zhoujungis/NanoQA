"""高级搜索 q 解析 + 列表筛选组合。"""
from django.test import SimpleTestCase

from apps.testcases.services.search import parse_q
from apps.testcases.tests.base import NanoTestCase


class ParseQTests(SimpleTestCase):
    """q 解析器单测（不落库）。"""

    def test_structured_tokens(self):
        search = parse_q("priority:P0 status:active module:login tag:smoke automation:automated")
        self.assertEqual(search.priority, ["P0"])
        self.assertEqual(search.status, ["active"])
        self.assertEqual(search.module, ["login"])
        self.assertEqual(search.tag, ["smoke"])
        self.assertEqual(search.automation, ["automated"])
        self.assertEqual(search.text, [])

    def test_invalid_value_degrades_to_text(self):
        search = parse_q("priority:PX status:nope automation:auto")
        self.assertEqual(search.priority, [])
        self.assertEqual(search.status, [])
        self.assertEqual(search.automation, [])
        self.assertEqual(search.text, ["priority:PX", "status:nope", "automation:auto"])

    def test_unknown_key_degrades_to_text(self):
        search = parse_q("owner:me foo:bar")
        self.assertEqual(search.text, ["owner:me", "foo:bar"])

    def test_empty_value_and_plain_words_degrade_to_text(self):
        search = parse_q("priority: 登录 smoke:")
        self.assertEqual(search.text, ["priority:", "登录", "smoke:"])

    def test_keys_and_values_are_case_insensitive(self):
        search = parse_q("Priority:p0 STATUS:Active AUTOMATION:Automated")
        self.assertEqual(search.priority, ["P0"])
        self.assertEqual(search.status, ["active"])
        self.assertEqual(search.automation, ["automated"])

    def test_tokens_combine_with_and_semantics(self):
        search = parse_q("P0 关键词 tag:a tag:b priority:P1")
        self.assertEqual(search.priority, ["P1"])
        self.assertEqual(search.tag, ["a", "b"])
        self.assertEqual(search.text, ["P0", "关键词"])

    def test_empty_query(self):
        search = parse_q("")
        self.assertEqual(search.priority, [])
        self.assertEqual(search.text, [])


class SearchApiTests(NanoTestCase):
    def _seed(self):
        self.login_case = self.create_case(
            title="登录成功",
            priority="P0",
            status="active",
            module_id=self.module.id,
            tag_ids=[self.tag_smoke.id],
            description="用户登录主流程",
            expected_result="登录成功进入首页",
        )
        self.cart_case = self.create_case(
            title="购物车结算",
            priority="P1",
            module_id=self.child_module.id,
            tag_ids=[self.tag_fast.id],
            expected_result="结算页展示金额",
        )
        self.reset_case = self.create_case(
            title="Login password reset",
            priority="P2",
            expected_result="重置邮件已发送",
        )
        return self.login_case, self.cart_case, self.reset_case

    def _ids(self, **params):
        return [item["id"] for item in self.list_cases(**params)["items"]]

    def test_q_structured_tokens(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(q="priority:P0"), [login["id"]])
        self.assertEqual(self._ids(q="status:active"), [login["id"]])
        self.assertEqual(self._ids(q="priority:P1 status:active"), [])
        self.assertEqual(self._ids(q="tag:smoke"), [login["id"]])
        self.assertEqual(sorted(self._ids(q="automation:manual")), sorted([login["id"], cart["id"], reset["id"]]))

    def test_q_module_token_matches_module_name(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(q="module:Login"), [login["id"]])

    def test_q_free_text_searches_content_fields(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(q="购物车"), [cart["id"]])
        self.assertEqual(self._ids(q="password"), [reset["id"]])  # title
        self.assertEqual(self._ids(q="登录主流程"), [login["id"]])  # description
        self.assertEqual(self._ids(q="进入首页"), [login["id"]])  # 当前版本 expected_result
        self.assertEqual(self._ids(q="购物车 金额"), [cart["id"]])  # 多词 AND
        self.assertEqual(self._ids(q="购物车 首页"), [])

    def test_q_invalid_token_is_plain_text(self):
        self._seed()
        self.assertEqual(self._ids(q="priority:PX"), [])

    def test_query_param_filters(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(priority="P0"), [login["id"]])
        self.assertEqual(self._ids(status="active"), [login["id"]])
        self.assertEqual(self._ids(owner_id=self.user.id), [])
        self.assertEqual(self._ids(tag="fast"), [cart["id"]])
        self.assertEqual(sorted(self._ids(automation_status="manual")), sorted([login["id"], cart["id"], reset["id"]]))
        self.assertEqual(self._ids(priority="P1", tag="fast"), [cart["id"]])

    def test_module_filter_with_submodules(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(module_id=self.root_module.id), [])
        self.assertEqual(
            sorted(self._ids(module_id=self.root_module.id, include_submodules="1")),
            sorted([login["id"], cart["id"]]),
        )
        self.assertEqual(self._ids(module_id=self.module.id), [login["id"]])
        self.assertEqual(
            sorted(self._ids(module_id=self.module.id, include_submodules="1")),
            sorted([login["id"], cart["id"]]),
        )

    def test_ordering(self):
        login, cart, reset = self._seed()
        self.assertEqual(self._ids(ordering="case_key"), [login["id"], cart["id"], reset["id"]])
        self.assertEqual(self._ids(ordering="-case_key"), [reset["id"], cart["id"], login["id"]])
        self.assertEqual(self._ids(ordering="priority"), [login["id"], cart["id"], reset["id"]])

    def test_invalid_filter_params_rejected(self):
        self._seed()
        for params in ({"ordering": "unknown"}, {"priority": "PX"}, {"module_id": "abc"},
                       {"created_at_start": "not-a-date"}):
            response = self.client.get(self.list_url, params)
            self.assertEqual(response.status_code, 400, params)
            self.assertEqual(response.json()["code"], 40006)

    def test_list_is_paginated_and_prefetch_friendly(self):
        self._seed()
        data = self.list_cases(page=1, page_size=2)
        self.assertEqual(set(data), {"items", "total", "page", "page_size"})
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["items"]), 2)
        item = data["items"][0]
        self.assertIn("case_key", item)
        self.assertIn("precondition_summary", item)
        self.assertIn("tags", item)
        self.assertIn("updated_at", item)
