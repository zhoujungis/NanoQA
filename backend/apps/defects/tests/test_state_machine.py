"""缺陷状态机测试（§50，含 D5b 回退转移）：全矩阵合法/非法转移。"""
from apps.defects.tests.base import NanoAPITestCase

# 独立契约表：与 common/statemachine.py 保持一致，作为行为断言
DEFECT_MATRIX = {
    "Open": {"In Progress", "Rejected", "Duplicate", "Closed"},
    "In Progress": {"Resolved", "Open", "Rejected", "Duplicate"},
    "Resolved": {"Closed", "Reopened", "In Progress"},
    "Reopened": {"In Progress", "Resolved", "Open"},
    "Closed": {"Reopened"},
    "Rejected": {"Open"},
    "Duplicate": {"Open"},
}
STATUSES = ["Open", "In Progress", "Resolved", "Reopened", "Closed", "Rejected", "Duplicate"]


class DefectStateMachineTests(NanoAPITestCase):
    def patch_status(self, defect, to_status):
        return self.client.patch(
            f"/api/v1/defects/{defect.pk}/",
            {"status": to_status, "updated_at": defect.updated_at.isoformat()},
            format="json",
        )

    def test_full_transition_matrix(self):
        self.login(self.qa)
        for from_status in STATUSES:
            for to_status in STATUSES:
                defect = self.make_defect(status=from_status)
                r = self.patch_status(defect, to_status)
                msg = f"{from_status} -> {to_status}"
                if from_status == to_status or to_status in DEFECT_MATRIX[from_status]:
                    self.assertEqual(r.status_code, 200, msg=msg)
                    self.assertEqual(self.assertCode(r, 0)["status"], to_status, msg=msg)
                else:
                    self.assertEqual(r.status_code, 400, msg=msg)
                    self.assertEqual(r.json()["code"], 40004, msg=msg)

    def test_rollback_transitions(self):
        """D5b 回退：Closed→Reopened、Rejected→Open、Duplicate→Open 合法。"""
        self.login(self.qa)
        for from_status, to_status in (("Closed", "Reopened"), ("Rejected", "Open"), ("Duplicate", "Open")):
            defect = self.make_defect(status=from_status)
            r = self.patch_status(defect, to_status)
            self.assertEqual(r.status_code, 200, msg=f"{from_status}->{to_status}")
            self.assertEqual(self.assertCode(r, 0)["status"], to_status)

    def test_open_to_resolved_illegal(self):
        """Open→Resolved 非法：400 + code 40004，状态不变。"""
        self.login(self.qa)
        defect = self.make_defect(status="Open")
        r = self.patch_status(defect, "Resolved")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], 40004)
        defect.refresh_from_db()
        self.assertEqual(defect.status, "Open")

    def test_transition_audit_action(self):
        self.login(self.qa)
        defect = self.make_defect(status="Open")
        r = self.patch_status(defect, "In Progress")
        self.assertCode(r, 0)
        from apps.audit.models import AuditLog

        log = AuditLog.objects.get(object_type="defect", object_id=defect.pk, action="transition")
        self.assertEqual(log.old_data.get("status"), "Open")
        self.assertEqual(log.new_data.get("status"), "In Progress")
