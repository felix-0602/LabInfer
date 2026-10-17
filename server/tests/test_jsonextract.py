from app.jsonextract import extract_json


def test_fenced_json():
    text = '总体线性良好。\n```json\n[{"a": 1}]\n```'
    assert extract_json(text) == [{"a": 1}]


def test_array_after_prose():
    text = '说明几句话。[{"type": "pattern", "text": "R2=0.99"}]'
    assert extract_json(text)[0]["type"] == "pattern"


def test_braces_inside_strings_do_not_break_scan():
    text = '人话。[{"text": "含 } 与 { 的字符串", "n": 2}]'
    obj = extract_json(text)
    assert obj[0]["n"] == 2


def test_garbage_returns_none():
    assert extract_json("完全没有 JSON") is None
    assert extract_json("") is None
