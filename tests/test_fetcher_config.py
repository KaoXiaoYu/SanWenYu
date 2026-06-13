from types import SimpleNamespace

from sanwenyu import config
from sanwenyu.problems import fetcher


def test_find_all_tex_images_preserves_generic_statement_images():
    formulas, graphics = fetcher.find_all_tex_images(
        '<p>x</p><img class="tex-formula" src="/formula.png">'
        '<img src="/diagram.png" alt="diagram">'
    )

    assert [item["src"] for item in formulas] == ["/formula.png"]
    assert [item["src"] for item in graphics] == ["/diagram.png"]


def test_qwen_config_uses_yaml_config_when_env_missing(monkeypatch):
    monkeypatch.setattr(fetcher, "QWEN_API_KEY", "")
    monkeypatch.setattr(fetcher, "QWEN_BASE_URL", "https://env.example/v1")
    monkeypatch.setattr(fetcher, "QWEN_MODEL", "")
    monkeypatch.setattr(
        config,
        "_config",
        SimpleNamespace(
            qwen_api_key="sk-from-config",
            qwen_base_url="https://dashscope.example/v1/",
            qwen_model="qwen-vl-test",
        ),
    )
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)

    assert fetcher._qwen_config() == (
        "sk-from-config",
        "https://dashscope.example/v1",
        "qwen-vl-test",
    )
