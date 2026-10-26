"""重复用例检测（§42）：difflib.SequenceMatcher 对 title+steps 文本做相似度。"""
from difflib import SequenceMatcher

from apps.testcases.models import TestCase, TestCaseVersion

SIMILARITY_THRESHOLD = 0.6
MAX_PAIRS = 50


def _case_texts(project) -> list[tuple[int, str]]:
    cases = list(TestCase.objects.filter(project=project).order_by("id"))
    if not cases:
        return []
    latest_version: dict[int, TestCaseVersion] = {}
    versions = TestCaseVersion.objects.filter(test_case__in=cases).order_by("test_case_id", "-version")
    for version in versions:
        latest_version.setdefault(version.test_case_id, version)

    texts = []
    for case in cases:
        version = latest_version.get(case.id)
        steps_text = ""
        if version:
            steps_text = " ".join(
                f"{step.get('action', '')} {step.get('expected', '')}" for step in (version.steps or [])
            )
        texts.append((case.id, f"{case.title} {steps_text}".strip()))
    return texts


def find_duplicates(project) -> list[dict]:
    """返回 [{case_a, case_b, similarity}]，≥阈值才输出，按相似度降序，最多 50 对。"""
    texts = _case_texts(project)
    pairs = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            id_a, text_a = texts[i]
            id_b, text_b = texts[j]
            similarity = SequenceMatcher(None, text_a, text_b).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                pairs.append({
                    "case_a": id_a,
                    "case_b": id_b,
                    "similarity": round(similarity, 4),
                })
    pairs.sort(key=lambda item: (-item["similarity"], item["case_a"], item["case_b"]))
    return pairs[:MAX_PAIRS]
