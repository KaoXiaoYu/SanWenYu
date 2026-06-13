import asyncio
import base64
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_build_notes_message_translates_and_formats():
    from sanwenyu.handlers.cmd import newproblem

    async def _run():
        stmt = {"notes": "Line A<br />Line B"}
        with patch.object(
            newproblem,
            "translate_sample_notes",
            AsyncMock(return_value=("第一行\n第二行", "")),
        ) as mocked_translate:
            result = await newproblem._build_notes_message(stmt)
        assert result == "样例解释：\n第一行\n第二行"
        mocked_translate.assert_awaited_once_with("Line A\nLine B")

    asyncio.run(_run())


def test_build_notes_message_does_not_fall_back_to_english_original():
    from sanwenyu.handlers.cmd import newproblem

    async def _run():
        stmt = {
            "notes": (
                '<div class="x">First line</div>'
                '<div class="x">Second &amp; line</div>'
            )
        }
        with patch.object(
            newproblem,
            "translate_sample_notes",
            AsyncMock(return_value=(None, "")),
        ):
            result = await newproblem._build_notes_message(stmt)
        assert result == ""

    asyncio.run(_run())


def test_problem_content_removes_emoji_but_keeps_digits_and_latex():
    from sanwenyu.handlers.cmd.newproblem import _sanitize_problem_content

    text = "计算 1️ 到 10 的答案 😄，满足 $a_i \\le n$。"
    assert _sanitize_problem_content(text) == "计算 1 到 10 的答案 ，满足 $a_i \\le n$。"


def test_build_notes_message_keeps_model_output_verbatim():
    from sanwenyu.handlers.cmd import newproblem

    async def _run():
        stmt = {"notes": "placeholder"}
        raw = (
            "A \\xrightarrow[l=1,\\,r=6]{} B, and x \\lt y \\gt z, "
            "with p \\leq q \\ge r and s \\oplus t."
        )
        with patch.object(
            newproblem,
            "translate_sample_notes",
            AsyncMock(return_value=(raw, "")),
        ):
            result = await newproblem._build_notes_message(stmt)
        assert result == f"样例解释：\n{raw}"

    asyncio.run(_run())


def test_build_notes_message_returns_empty_on_translate_exception():
    from sanwenyu.handlers.cmd import newproblem

    async def _run():
        stmt = {"notes": "Line A<br />Line B"}
        with patch.object(
            newproblem,
            "translate_sample_notes",
            AsyncMock(side_effect=RuntimeError("llm down")),
        ):
            result = await newproblem._build_notes_message(stmt)
        assert result == ""

    asyncio.run(_run())


def test_build_statement_image_messages_extracts_and_deduplicates_images():
    from sanwenyu.handlers.cmd.newproblem import _build_statement_image_messages

    payload = base64.b64encode(b"original-image").decode()
    stmt = {
        "render_html": (
            f'<p>before</p><img class="tex-graphics" '
            f'src="data:image/png;base64,{payload}">'
            f'<img src="data:image/png;base64,{payload}">'
        )
    }

    assert _build_statement_image_messages(stmt) == [[{
        "type": "image",
        "data": {"file": f"base64://{payload}"},
    }]]


def test_build_statement_image_messages_ignores_invalid_data():
    from sanwenyu.handlers.cmd.newproblem import _build_statement_image_messages

    stmt = {"render_html": '<img src="data:image/png;base64,not-valid!!!">'}
    assert _build_statement_image_messages(stmt) == []


def test_send_problem_forward_card_includes_statement_image_nodes():
    from sanwenyu.handlers.cmd import newproblem

    async def _run():
        forwarded = []
        send_private = AsyncMock(side_effect=[101, 102, 103])

        async def _send_forward(group_id, nodes):
            forwarded.append((group_id, nodes))
            return 201

        with patch.object(
            newproblem,
            "get_config",
            return_value=SimpleNamespace(bot_qq=999),
        ), patch.object(
            newproblem,
            "render_text_to_png",
            AsyncMock(side_effect=["problem.png", "sample.png"]),
        ), patch.object(
            newproblem,
            "image_message_from_path",
            side_effect=lambda path: [{"type": "image", "data": {"file": path}}],
        ), patch.object(
            newproblem,
            "send_private_msg",
            send_private,
        ), patch.object(
            newproblem,
            "send_group_forward_msg",
            _send_forward,
        ), patch.object(
            newproblem.asyncio,
            "sleep",
            AsyncMock(),
        ):
            result, payload = await newproblem._send_problem_forward_card(
                group_id=123,
                post_msg="problem",
                sample_messages=["sample"],
                snake_enabled=False,
                statement_image_messages=[[
                    {"type": "image", "data": {"file": "base64://original"}},
                ]],
            )

        assert result == 201
        assert payload["statement_image_msg_ids"] == [102]
        assert forwarded == [(
            123,
            [
                {"type": "node", "data": {"id": "101"}},
                {"type": "node", "data": {"id": "102"}},
                {"type": "node", "data": {"id": "103"}},
            ],
        )]

    asyncio.run(_run())
