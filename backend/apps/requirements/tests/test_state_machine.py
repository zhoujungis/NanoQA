"""需求状态机测试（§50，含 D5b 回退转移）。"""
from apps.audit.models import AuditLog
from apps.requirements.tests.base import NanoAPITestCase

# 独立契约表：与 common/statemachine.py 保持一致，作为行为断言
REQUIREMENT_MATRIX = {
    "draft": {"ready", "cancelled"},
    "ready": {"draft", "in_progress", "cancelled"},
    "in_progress": {"done", "ready", "cancelled"},
    "done": {"in_progress"},
    "cancelled": {"draft"},
}
STATUSES = ["draft", "ready", "in_progress", "done", "cancelled"]


class RequirementStateMachineTests(NanoAPITestCase):
    def patch_status(self, req, to_status):
        return self.client.patch(
            f"/api/v1/requirements/{req.pk}/",
            {"status": to_status, "updated_at": req.updated_at.isoformat()},
            format="json",
        )

    def test_full_transition_matrix(self):
        self.login(self.manager)
        for from_status in STATUSES:
            for to_status in STATUSES:
                req = self.make_requirement(status=from_status)
                r = self.patch_status(req, to_status)
                msg = f"{from_status} -> {to_status}"
                if from_status == to_status or to_status in REQUIREMENT_MATRIX[from_status]:
                    self.assertEqual(r.status_code, 200, msg=msg)
                    data = self.assertCode(r, 0)
                    self.assertEqual(data["status"], to_status, msg=msg)
                else:
                    self.assertEqual(r.status_code, 400, msg=msg)
                    self.assertEqual(r.json()["code"], 40004, msg=msg)

    def test_rollback_transitions_allowed(self):
        """D5b 回退：done→in_progress、cancelled→draft、ready→draft 均合法。"""
        self.login(self.manager)
        for from_status, to_status in (("done", "in_progress"), ("cancelled", "draft"), ("ready", "draft")):
            req = self.make_requirement(status=from_status)
            r = self.patch_status(req, to_status)
            self.assertEqual(r.status_code, 200, msg=f"{from_status}->{to_status}")
            self.assertEqual(self.assertCode(r, 0)["status"], to_status)

    def test_illegal_transition_records_no_audit(self):
        self.login(self.manager)
        req = self.make_requirement(status="draft")
        r = self.patch_status(req, "done")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], 40004)
        req.refresh_from_db()
        self.assertEqual(req.status, "draft")
        self.assertFalse(AuditLog.objects.filter(object_type="requirement", object_id=req.pk).exists())

    def test_transition_audit_action(self):
        self.login(self.manager)
        req = self.make_requirement(status="draft")
        r = self.patch_status(req, "ready")
        self.assertCode(r, 0)
        log = AuditLog.objects.get(object_type="requirement", object_id=req.pk, action="transition")
        self.assertEqual(log.old_data.get("status"), "draft")
        self.assertEqual(log.new_data.get("status"), "ready")
