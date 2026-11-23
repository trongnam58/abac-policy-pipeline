# -*- coding: utf-8 -*-
"""Chạy demo Streamlit ở chế độ headless (bỏ qua nếu chưa cài streamlit)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_demo_renders_paper_example_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    codes = " ".join(c.value for c in at.code)
    assert "u.subject.actions.objects.roster->notEmpty()" in codes
    assert "associationclass Context between" in codes


def test_demo_handles_vietnamese_example():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.selectbox[0].select("Tiếng Việt").run()
    assert not at.exception
    assert any("Learning_Material" in c.value or "Score.allInstances" in c.value for c in at.code)
