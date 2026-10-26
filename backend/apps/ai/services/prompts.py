"""Prompt 模板加载：模板统一放 apps/ai/prompts/*.txt，禁止写在 View 里（§67）。"""
from pathlib import Path
from string import Template

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str, **context) -> str:
    template = (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return Template(template).substitute(**context)
