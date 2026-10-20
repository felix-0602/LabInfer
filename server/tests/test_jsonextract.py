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


def test_pure_json_object_with_nested_arrays():
    """M2 事故回归：裸 JSON 对象不能被内部的嵌套数组偷走（曾返回 ticks 数组导致
    「识别结果缺少 axes」）。"""
    text = '{"plot_area":{"u0":1},"axes":{"x":{"ticks":[{"px":[352,1250],"value":0}]}},"series":[]}'
    obj = extract_json(text)
    assert isinstance(obj, dict) and "axes" in obj


def test_positional_first_wins():
    """混合文本里对象与数组谁先出现取谁，不再按类型偏好。"""
    assert extract_json('见 {"a":1} 与 [1,2]') == {"a": 1}
    assert extract_json('见 [1,2] 与 {"a":1}') == [1, 2]
