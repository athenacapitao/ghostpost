"""Tests for src/security/sanitizer.py — Layer 1+2 input sanitization."""

import pytest

from src.security.sanitizer import (
    ISOLATION_END,
    ISOLATION_START,
    is_isolated,
    isolate_content,
    sanitize_html,
    sanitize_plain,
)


class TestSanitizeHtml:
    def test_none_returns_empty_string(self) -> None:
        assert sanitize_html(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        assert sanitize_html("") == ""

    def test_removes_html_comments(self) -> None:
        result = sanitize_html("Hello <!-- hidden injection --> World")
        assert "<!--" not in result
        assert "hidden injection" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_multiline_html_comments(self) -> None:
        result = sanitize_html("Before\n<!-- line1\nline2\nline3 -->\nAfter")
        assert "<!--" not in result
        assert "line1" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_script_tags(self) -> None:
        result = sanitize_html("Safe <script>alert('xss')</script> text")
        assert "<script>" not in result
        assert "alert" not in result
        assert "Safe" in result
        assert "text" in result

    def test_removes_script_tags_case_insensitive(self) -> None:
        result = sanitize_html("<SCRIPT>evil()</SCRIPT>")
        assert "SCRIPT" not in result.upper() or "<SCRIPT>" not in result

    def test_removes_style_tags(self) -> None:
        result = sanitize_html("Text <style>.hide{display:none}</style> more")
        assert "<style>" not in result
        assert ".hide" not in result
        assert "Text" in result

    def test_removes_event_handlers(self) -> None:
        result = sanitize_html('<a href="/" onclick="steal()">link</a>')
        assert "onclick" not in result
        assert "steal" not in result

    def test_removes_onload_handler(self) -> None:
        result = sanitize_html('<img src="x" onload="bad()">')
        assert "onload" not in result
        assert "bad" not in result

    def test_decodes_html_entities(self) -> None:
        result = sanitize_html("&lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot;")
        assert "<b>bold</b>" in result
        assert '"quoted"' in result

    def test_normalizes_whitespace(self) -> None:
        result = sanitize_html("hello    world\n\n  multiple  spaces")
        assert "  " not in result
        assert "hello world" in result

    def test_plain_text_passthrough(self) -> None:
        text = "This is a normal email body."
        result = sanitize_html(text)
        assert result == text

    def test_removes_script_with_attributes(self) -> None:
        result = sanitize_html('<script type="text/javascript">evil()</script>')
        assert "evil" not in result


class TestSanitizePlain:
    def test_none_returns_empty_string(self) -> None:
        assert sanitize_plain(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        assert sanitize_plain("") == ""

    def test_removes_null_bytes(self) -> None:
        result = sanitize_plain("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_removes_control_characters(self) -> None:
        # Bell (\x07), backspace (\x08), form feed (\x0c)
        result = sanitize_plain("test\x07\x08\x0cvalue")
        assert "\x07" not in result
        assert "\x08" not in result
        assert "\x0c" not in result

    def test_preserves_newline_and_tab(self) -> None:
        text = "line1\nline2\ttabbed"
        result = sanitize_plain(text)
        assert "\n" in result
        assert "\t" in result

    def test_strips_leading_trailing_whitespace(self) -> None:
        result = sanitize_plain("  hello world  ")
        assert result == "hello world"

    def test_plain_text_passthrough(self) -> None:
        text = "Normal email text with\nnewlines and\ttabs."
        result = sanitize_plain(text)
        assert result == text

    def test_removes_delete_char(self) -> None:
        result = sanitize_plain("text\x7fmore")
        assert "\x7f" not in result


class TestIsolateContent:
    def test_wraps_content_with_markers(self) -> None:
        result = isolate_content("email body here")
        assert result.startswith(ISOLATION_START)
        assert result.endswith(ISOLATION_END)
        assert "email body here" in result

    def test_markers_on_separate_lines(self) -> None:
        result = isolate_content("content")
        lines = result.split("\n")
        assert lines[0] == ISOLATION_START
        assert lines[-1] == ISOLATION_END

    def test_empty_content_wrapped(self) -> None:
        result = isolate_content("")
        assert ISOLATION_START in result
        assert ISOLATION_END in result


class TestIsIsolated:
    def test_properly_isolated_content_returns_true(self) -> None:
        content = isolate_content("some email text")
        assert is_isolated(content) is True

    def test_raw_content_returns_false(self) -> None:
        assert is_isolated("just plain text") is False

    def test_only_start_marker_returns_false(self) -> None:
        assert is_isolated(f"{ISOLATION_START}\ncontent") is False

    def test_only_end_marker_returns_false(self) -> None:
        assert is_isolated(f"content\n{ISOLATION_END}") is False

    def test_empty_string_returns_false(self) -> None:
        assert is_isolated("") is False
