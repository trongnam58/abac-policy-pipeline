# -*- coding: utf-8 -*-
"""Kiểm chứng mô hình + bất biến bằng công cụ USE (UML-based Specification Environment).

Cấu hình: đặt ABAC_USE_HOME trỏ tới thư mục USE (chứa lib/use-gui.jar), cần Java 21+.
  - compile_spec(path)       : `use -c model.use` — parse + type-check đặc tả và OCL
  - check_state(use, soil)   : nạp thể hiện SOIL rồi chạy lệnh `check` trên trạng thái
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

TIMEOUT_SECONDS = 300
_ERROR_LINE = re.compile(r"(?:^|\n)[^\n]*?:\d+:\d+:[^\n]*|(?:^|\n)\s*Error:[^\n]*")
_STATE_PROBLEM = re.compile(r"[^\n]*(?:Multiplicity constraint violation|checking invariant \(\d+\) `[^`]+': FAILED)[^\n]*")


@dataclass
class UseResult:
    ok: bool
    command: list[str]
    output: str
    errors: list[str]


def find_use_jar() -> str | None:
    home = os.environ.get("ABAC_USE_HOME")
    if not home:
        return None
    jar = os.path.join(home, "lib", "use-gui.jar")
    return jar if os.path.isfile(jar) else None


def available() -> bool:
    return find_use_jar() is not None and shutil.which("java") is not None


def _run(args: list[str], stdin: str = "") -> UseResult:
    jar = find_use_jar()
    if jar is None:
        raise RuntimeError("Chưa cấu hình ABAC_USE_HOME (thư mục cài USE chứa lib/use-gui.jar)")
    java = shutil.which("java")
    if java is None:
        raise RuntimeError("Không tìm thấy 'java' trong PATH (USE cần Java 21+)")
    cmd = [java, "-jar", jar, "-nr", *args]
    try:
        proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        return UseResult(ok=False, command=cmd, output=str(exc.output or ""),
                         errors=[f"USE quá thời gian {TIMEOUT_SECONDS}s"])
    output = (proc.stdout or "") + (proc.stderr or "")
    errors = [m.strip() for m in _ERROR_LINE.findall(output)]
    return UseResult(ok=proc.returncode == 0 and not errors, command=cmd,
                     output=output, errors=errors)


def compile_spec(use_path: str) -> UseResult:
    return _run(["-c", use_path])


def check_state(use_path: str, soil_path: str) -> UseResult:
    """Nạp đặc tả + kịch bản SOIL ở chế độ không GUI; kết quả `check` nằm trong output."""
    result = _run(["-nogui", use_path, soil_path], stdin="exit\n")
    problems = [m.strip() for m in _STATE_PROBLEM.findall(result.output)]
    result.errors += problems
    result.ok = result.ok and not problems
    return result


_CHECKED = re.compile(r"checked (\d+) invariants? in [^,]+, (\d+) failures?")


@dataclass
class SemanticResult:
    ok: bool
    invariants: int
    compliant_failures: int | None   # mong đợi 0
    violating_failures: int | None   # mong đợi = invariants
    detail: str


def semantic_check(use_path: str, soil_path: str) -> SemanticResult:
    """Chạy kịch bản 2 trạng thái (tuân thủ / vi phạm) do use_model.semantic_check_soil sinh."""
    result = _run(["-nogui", use_path, soil_path], stdin="exit\n")
    checks = [(int(n), int(f)) for n, f in _CHECKED.findall(result.output)]
    if len(checks) != 2:
        return SemanticResult(False, 0, None, None,
                              "USE không chạy đủ 2 lần check: " + " | ".join(result.errors[:5]))
    (n, compliant), (_, violating) = checks
    ok = result.ok and n > 0 and compliant == 0 and violating == n
    return SemanticResult(ok, n, compliant, violating, "" if ok else result.output[-2000:])
