from src.llm_reasoner import PARA_TEMPLATE, build_prompt


def test_para_template_format():
    target = "This is a test paragraph."
    prompt = build_prompt(PARA_TEMPLATE, target, [], [])
    # Ensure the placeholder is replaced and content present
    assert "This is a test paragraph." in prompt
    assert "TARGET" in prompt  # basic sanity
