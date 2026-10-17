from app.validator import collect_numbers, validate_findings


def _fixtures():
    analysis = {
        "fits": [{"dataset_id": "ds1", "slope": 0.4026, "intercept": 0.0021, "r2": 0.9999, "n": 7}],
        "predictions": [{"dataset_id": "ds1", "point_id": "s1", "value": 0.556,
                         "u95": 0.0846, "as_reported": 2.78}],
        "residuals": [],
        "qc_results": [{"rule_id": "calibration_r2", "pass": True, "value": 0.9999,
                        "citation": "HJ 535-2009"}],
        "comparison": {
            "vs_reference": [{"mine_slope": 0.4026, "ref_slope": 0.13933}],
            "vs_limit": [{"point_id": "s1", "value": 2.78, "limit": 1.0, "verdict": "exceed"}],
            "vs_crm": {"measured": 0.721, "certified": 0.716, "u95": 0.044},
        },
    }
    dataset = {"id": "ds1", "rows": [{"id": "s1", "series": "sample:x"}]}
    ctx = {"reference": {"limits": [{"label": "GB 3838-2002 III 类", "value": 1.0}]}}
    return analysis, dataset, ctx


def test_valid_finding_passes_with_label_numbers():
    analysis, dataset, ctx = _fixtures()
    f = [{"type": "conclusion",
          "text": "样品浓度 2.78 mg/L，超过 GB 3838-2002 III 类限值（1.0）。",
          "evidence": [{"type": "point", "dataset_id": "ds1", "point_id": "s1"},
                       {"type": "comparison", "target": "vs_limit[0]"}]}]
    kept, dropped = validate_findings(f, analysis, dataset, ctx)
    assert len(kept) == 1 and not dropped


def test_fabricated_number_dropped():
    analysis, dataset, ctx = _fixtures()
    f = [{"type": "pattern", "text": "活化能为 99.9 kJ/mol。",
          "evidence": [{"type": "fit", "dataset_id": "ds1"}]}]
    kept, dropped = validate_findings(f, analysis, dataset, ctx)
    assert not kept and "99.9" in dropped[0]


def test_dangling_evidence_dropped():
    analysis, dataset, ctx = _fixtures()
    f = [{"type": "anomaly", "text": "点 p9 偏离 2.78。",
          "evidence": [{"type": "point", "dataset_id": "ds1", "point_id": "p9"}]},
         {"type": "qc", "text": "规则 calibration_r2 通过。",
          "evidence": [{"type": "comparison", "target": "vs_limit[9]"}]}]
    kept, dropped = validate_findings(f, analysis, dataset, ctx)
    assert not kept and len(dropped) == 2


def test_numbers_collected_from_strings():
    nums = collect_numbers({"label": "GB 3838-2002", "nested": ["HJ 630-2011"]})
    # 连字符按负号提取；文本侧与白名单侧使用同一正则，语义一致
    assert {3838.0, -2002.0, 630.0, -2011.0} <= set(nums)
