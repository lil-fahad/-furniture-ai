import os
from pathlib import Path
from typing import Optional

from openai import OpenAI


class CodexAutoDev:
    """
    Utility wrapper around the OpenAI API for common code-editing workflows.

    - AutoFix: إصلاح الأخطاء
    - AutoRefactor: تحسين الأكواد
    - AutoRewrite: إعادة كتابة ملف بالكامل
    - AutoGenerate: إنشاء ملفات جديدة بالكامل
    - FileIO: قراءة + كتابة الملفات
    """

    def __init__(self, base_path: Optional[Path] = None, api_key: Optional[str] = None) -> None:
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.base = base_path or Path(__file__).resolve().parent.parent

    def read_file(self, rel_path: str) -> str:
        path = self.base / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_file(self, rel_path: str, content: str) -> str:
        path = self.base / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def ask_codex(self, system_msg: str, user_msg: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content or ""

    # AUTO FIX — تصحيح الأكواد
    def auto_fix(self, rel_path: str, issue_description: str):
        old_code = self.read_file(rel_path)
        system_prompt = (
            "You are Codex AutoFix. Fix all bugs, syntax errors, missing imports, "
            "runtime issues, undefined variables, and logic errors. "
            "Return ONLY the fixed code with no explanation."
        )
        user_prompt = f"""
        FILE PATH: {rel_path}
        ISSUE DESCRIPTION: {issue_description}

        OLD CODE:
        {old_code}
        """
        new_code = self.ask_codex(system_prompt, user_prompt)
        self.write_file(rel_path, new_code)
        return {"file": rel_path, "status": "auto_fixed"}

    # AUTO REFACTOR — تحسين الأكواد بالكامل
    def auto_refactor(self, rel_path: str, style: str = "clean"):
        old_code = self.read_file(rel_path)
        system_prompt = (
            "You are Codex Refactor. Improve the code readability, performance, "
            "structure, naming conventions, remove duplication, and apply clean architecture. "
            "Do NOT add comments. Return ONLY the final refactored code."
        )
        user_prompt = f"""
        FILE PATH: {rel_path}
        REFACTOR STYLE: {style}

        OLD CODE:
        {old_code}
        """
        new_code = self.ask_codex(system_prompt, user_prompt)
        self.write_file(rel_path, new_code)
        return {"file": rel_path, "status": "refactored"}

    # AUTO REWRITE — إعادة كتابة الملفات حسب طلب المستخدم
    def auto_rewrite(self, rel_path: str, instruction: str):
        old_code = self.read_file(rel_path)
        system_prompt = (
            "You are Codex AutoWriter. Rewrite the file according to the user instructions. "
            "Return ONLY the pure final code."
        )
        user_prompt = f"""
        FILE PATH: {rel_path}
        USER INSTRUCTION: {instruction}

        OLD CODE:
        {old_code}
        """
        new_code = self.ask_codex(system_prompt, user_prompt)
        self.write_file(rel_path, new_code)
        return {"file": rel_path, "status": "rewritten"}

    # AUTO GENERATE — إنشاء ملفات جديدة بالكامل
    def auto_generate(self, rel_path: str, description: str):
        system_prompt = (
            "You are Codex Generator. Create a new file with fully working code. "
            "Do not return explanations or comments. Only code."
        )
        new_code = self.ask_codex(system_prompt, description)
        self.write_file(rel_path, new_code)
        return {"file": rel_path, "status": "generated"}
