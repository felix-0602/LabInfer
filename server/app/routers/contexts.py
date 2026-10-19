import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION
from ..models import REGISTRY
from ..storage import new_id

router = APIRouter(prefix="/api/m3", tags=["m3"])

ALKALI_TITRATION_TEMPLATE = {
    "schema_version": CONTRACT_VERSION,
    "name": "HCl 标定与碱灰总碱度（GB/T 601-2016 无水碳酸钠法）",
    "purpose": "以基准无水碳酸钠标定 HCl 浓度，测定碱灰总碱度（以 Na₂O 计），检查平行测定精密度",
    "model": "titration_standardization",
    "model_params": {
        "molar_mass_na2co3_g_mol": 105.99,   # GB/T 601-2016：M(½Na₂CO₃) = 52.994
        "molar_mass_na2o_g_mol": 61.979,
        "stock_volume_ml": 250,              # 碱灰试液定容体积
        "aliquot_volume_ml": 25,             # 每次滴定移取试液体积
        # 0.7.0：滴定曲线与误差预算的常数（契约「滴定公式」节）
        "pka1": 6.35, "pka2": 10.33,         # 碳酸 25 ℃
        "initial_water_ml": 30,              # 溶解基准物的水量（教材 25～35 mL 取中值）
        "indicator": {"name": "甲基橙", "ph_range": [3.1, 4.4]},
        "balance_error_g": 0.0001,           # 单次称量最大误差，差减法计两次
        "burette_error_ml": 0.01,            # 单次读数最大误差，计两次
    },
    "guide": {   # 0.8.0 教学导读层，形状与 M8 前端约定一致，规则见 docs/wiki.md#表达标准
        "status": "reviewed",          # 离线撰写、出处已核；draft = AI 生成待核（前端挂提示）
        "audience_level": 3,           # 对齐 ladder.base_level：按哪一级读者写
        "generated_at": "2026-10-19T12:00:00Z",
        "sources": [
            {"source_id": "src_textbook_exp3", "title": "武汉工程大学《分析化学实验》",
             "locator": "实验 3 HCl 溶液的标定及碱灰总碱度的测定",
             "quote": "常以 HCl 标准溶液为滴定剂测定总碱度来衡量产品的质量", "verified": True},
            {"source_id": "src_ac_book", "title": "分析化学教材",
             "locator": "酸碱滴定章、误差与有效数字章、终点误差节、电位滴定章",
             "quote": None, "verified": True},
            {"source_id": "src_gb601", "title": "GB/T 601-2016 化学试剂 标准滴定溶液的制备",
             "locator": "盐酸标定条", "quote": "基准无水碳酸钠 270～300 ℃ 灼烧至恒重", "verified": True},
            {"source_id": "src_gb601_boil", "title": "GB/T 601-2016",
             "locator": "HCl 标定：近终点煮沸驱 CO₂ 条", "quote": None, "verified": False},
            {"source_id": "src_guide_online",
             "title": "湖南人文科技学院《分析化学实验》实验指导书（网络核实，2026-10）",
             "locator": "实验一 酸碱标准溶液的配制及标定",
             "quote": "称取 0.15～0.20 g 无水 Na₂CO₃ 3 份，滴至黄色恰变为橙色即为终点", "verified": True},
            {"source_id": "src_guide_online_dev",
             "title": "湖南人文科技学院《分析化学实验》实验指导书（网络核实，2026-10）",
             "locator": "实验一/实验二 精密度要求",
             "quote": "三次测定结果的平均偏差在 0.1% 之内；各次相对偏差应在 ±0.5% 以内", "verified": True},
            {"source_id": "src_guide_online_prep",
             "title": "湖南人文科技学院《分析化学实验》实验指导书（网络核实，2026-10）",
             "locator": "实验一 0.1 mol/L HCl 的配制",
             "quote": "量取浓盐酸约 9 mL，加水稀释至 1 L", "verified": True},
            {"source_id": "src_docs", "title": "LabInfer 产品与契约文档",
             "locator": "product.md 演示案例；contracts.md 滴定曲线参照", "quote": None, "verified": True},
            {"source_id": "src_jjf", "title": "JJF 1059.1-2012 测量不确定度评定与表示（GUM 国内版）",
             "locator": "扩展不确定度定义", "quote": None, "verified": True},
        ],
        "glossary": [
            {"term_id": "standardization", "term": "标定",
             "plain": "拿一份纯到可以完全信任、能称出准确克数的固体，反过来测出一瓶溶液的真实浓度",
             "help": "盐酸一边放一边挥发，自己定不准，只能靠更可靠的固体来定它",
             "aliases": [], "source": "src_textbook_exp3"},
            {"term_id": "primary_standard", "term": "基准物质",
             "plain": "纯到不会给结果带来偏差、放多久都不变质、能直接称量的固体，本实验用无水碳酸钠",
             "help": "它自己必须先准，才有资格去定别人的浓度",
             "aliases": ["基准物", "基准试剂"], "source": "src_textbook_exp3"},
            {"term_id": "titration", "term": "滴定",
             "plain": "把已知浓度的溶液从滴定管里一滴滴加入试样，到反应恰好完成，再用消耗的体积反算含量",
             "aliases": [], "source": "src_ac_book"},
            {"term_id": "titrant", "term": "滴定剂",
             "plain": "装在滴定管里逐滴加出的那种已知浓度溶液；本实验是盐酸",
             "aliases": [], "source": "src_ac_book"},
            {"term_id": "equivalence_point", "term": "化学计量点",
             "plain": "加入的酸恰好把碱完全中和的那个理论瞬间；肉眼看不见，只能推算",
             "aliases": ["计量点", "等当点"], "source": "src_ac_book"},
            {"term_id": "indicator", "term": "指示剂",
             "plain": "溶液酸碱性变到某个程度就改变颜色、替眼睛报「反应完成」信号的物质；本实验用甲基橙",
             "aliases": [], "source": "src_ac_book"},
            {"term_id": "titration_jump", "term": "滴定突跃",
             "plain": "碱刚好被反应完的前后，多加一滴酸、溶液酸碱性就大幅变化的一小段；指示剂必须在这一段内变色终点才准",
             "aliases": ["突跃"], "source": "src_ac_book"},
            {"term_id": "total_alkalinity", "term": "总碱度",
             "plain": "试样里所有能中和酸的碱性成分合起来的总量，统一折算成 Na₂O 的质量分数报告",
             "aliases": [], "source": "src_textbook_exp3"},
            {"term_id": "soda_ash", "term": "碱灰（工业纯碱）",
             "plain": "工业碳酸钠；主要成分 Na₂CO₃，还可能混少量 NaOH、NaHCO₃ 和不与酸反应的杂质",
             "aliases": ["纯碱", "苏打"], "source": "src_textbook_exp3"},
            {"term_id": "parallel_determination", "term": "平行测定",
             "plain": "同一份试样独立完整地测几遍；结果彼此靠近才说明操作可信",
             "aliases": ["平行"], "source": "src_textbook_exp3"},
            {"term_id": "relative_average_deviation", "term": "相对平均偏差",
             "plain": "各次结果偏离平均值的平均幅度占平均值的百分比，衡量结果散得多开",
             "aliases": ["平均偏差"], "source": "src_textbook_exp3"},
            {"term_id": "systematic_error", "term": "系统误差",
             "plain": "让每次结果朝同一方向歪的误差，如基准物吸水；与之相对的随机误差让结果忽大忽小",
             "aliases": [], "source": "src_ac_book"},
            {"term_id": "buffering", "term": "缓冲",
             "plain": "溶液里有成分在抵抗 pH 变化的现象；本实验由溶解的 CO₂ 造成，会让突跃变缓",
             "aliases": ["缓冲作用"], "source": "src_ac_book"},
            {"term_id": "c_bar", "term": "平均浓度 c̄",
             "plain": "把几份浓度结果全部加起来、再除以份数得到的数，记号是在 c 上加一横",
             "help": "三份各测一次，取平均当作这支盐酸的浓度，比任何单份更可靠",
             "aliases": ["c̄"], "source": "src_ac_book"},
            {"term_id": "r_squared", "term": "拟合优度 R²",
             "plain": "说明各点在直线附近排得有多齐的一个数；最大是 1，1 就是所有点恰好落在一条直线上",
             "help": "越接近 1，各点越齐地贴在直线上，线性关系越可信",
             "aliases": ["R²", "决定系数"], "source": "src_ac_book"},
            {"term_id": "u95", "term": "不确定度 ±",
             "plain": "把每一步难免的小误差都算进去之后，估出的一个上下范围，记号是正负号",
             "help": "真实值有九成五的把握落在这个范围里，不是测量本身在晃",
             "aliases": ["±", "U95", "扩展不确定度"], "source": "src_jjf"},
            {"term_id": "regression_origin", "term": "过原点回归",
             "plain": "让直线必须经过原点（称 0 克就耗 0 毫升），再由各点算出这条直线的斜率",
             "help": "斜率就是每克碳酸钠该耗多少毫升盐酸，直接换算出浓度",
             "aliases": [], "source": "src_ac_book"},
            {"term_id": "dv", "term": "体积偏差 ΔV",
             "plain": "实际滴到变色所用的体积，减去理论上刚好反应完所需的体积，相差的毫升数",
             "help": "负数表示终点提前收了，正数表示拖后了",
             "aliases": ["ΔV"], "source": "src_docs"},
        ],
        "field_notes": {   # 键 = 上下文字段路径；01 页用人话替换原始键名，缺哪个显示原始键名
            "model": {"label": "分析模型",
                      "plain": "这套数据按什么路子算：先标定盐酸浓度，再算碱灰总碱度。"},
            "model_params.molar_mass_na2co3_g_mol": {"label": "Na₂CO₃ 摩尔质量",
                      "plain": "一摩尔（固定个数分子）无水碳酸钠的质量，把称出的克数换算成物质的量时用。"},
            "model_params.molar_mass_na2o_g_mol": {"label": "Na₂O 摩尔质量",
                      "plain": "总碱度统一折算成它来报告的折算基准。"},
            "model_params.stock_volume_ml": {"label": "试液定容体积",
                      "plain": "碱灰溶解后准确稀释到的总体积。"},
            "model_params.aliquot_volume_ml": {"label": "每次移取体积",
                      "plain": "每份滴定从试液里移出的体积。"},
            "model_params.pka1": {"label": "碳酸 pKa₁",
                      "plain": "碳酸分两步解离，这是第一步的强度常数；画理论滴定曲线用。"},
            "model_params.pka2": {"label": "碳酸 pKa₂",
                      "plain": "碳酸第二步解离的强度常数；画理论滴定曲线用。"},
            "model_params.initial_water_ml": {"label": "溶解水量",
                      "plain": "溶解基准碳酸钠用的水量（教材 25～35 mL 取中值）。"},
            "model_params.indicator": {"label": "指示剂",
                      "plain": "甲基橙，酸性强到一定程度时由黄变橙，替眼睛报「反应完成」。",
                      "term_id": "indicator"},
            "model_params.balance_error_g": {"label": "天平称量误差",
                      "plain": "差减法要称两次、误差相加；误差预算里称量项的来源。"},
            "model_params.burette_error_ml": {"label": "滴定管读数误差",
                      "plain": "一次滴定初读末读各一次、误差相加；误差预算里读数项的来源。"},
            "variables.m": {"label": "基准物称样质量",
                      "plain": "每份基准无水碳酸钠称了多少克。"},
            "variables.V": {"label": "HCl 滴定体积",
                      "plain": "滴到变色那一下累计消耗的盐酸毫升数。"},
            "variables.ms": {"label": "碱灰试样质量",
                      "plain": "这份工业纯碱一共称了多少克（定容 250 mL 的原料）。"},
            "qc_rules.standardization_rpad": {"label": "标定精密度检查",
                      "plain": "三份标定浓度的相对平均偏差不得超过 0.2%，超了说明手不稳。",
                      "term_id": "relative_average_deviation"},
            "qc_rules.parallel_rpd": {"label": "平行精密度检查",
                      "plain": "三份总碱度的相对平均偏差不得超过 0.2%。"},
            "qc_rules.outlier_grubbs": {"label": "离群值检查",
                      "plain": "格拉布斯检验判断某个可疑值是不是该剔除（GB/T 4883）。"},
            "reference.limits[0]": {"label": "总碱度参照上限",
                      "plain": "纯 Na₂CO₃ 的理论总碱度（以 Na₂O 计）；碱灰超过它，说明混了别的碱。"},
        },
        "sections": [
            {"section_id": "overview", "title": "这个实验在干什么：两步咬合",
             "show_in": ["context", "literature"], "order": 1, "rung_id": None,
             "summary": "先用很纯的碳酸钠把盐酸的真实浓度测准，再用这支盐酸去测碱灰的总碱度。",
             "body": "整个实验分两步，方向相反却互相咬合。第一步叫[标定](term:standardization)："
                     "浓盐酸一开瓶就在挥发，直接配不出准确浓度，所以先用天平称出几份很纯的"
                     "无水碳酸钠（[基准物质](term:primary_standard)），用它反过来把盐酸的真实浓度测准。"
                     "第二步叫测定：用这支浓度已知的盐酸去[滴定](term:titration)碱灰，"
                     "把里面所有能把酸「吃掉」的碱性成分合起来测成一个数，就是"
                     "[总碱度](term:total_alkalinity)。第一步的浓度差一点点，"
                     "第二步的结果就跟着差一点点。所以标定做得多细，直接决定整个实验可信到什么程度。",
             "terms": ["standardization", "primary_standard", "titration", "total_alkalinity"],
             "sources": ["src_textbook_exp3", "src_guide_online"]},
            {"section_id": "why-standardize", "title": "为什么浓度必须先标定，为什么选无水碳酸钠",
             "show_in": ["context"], "order": 2, "rung_id": None,
             "summary": "盐酸会挥发，浓度配不准；碳酸钠够纯够稳、摩尔质量大，称量误差小。",
             "body": "盐酸达不到直接配准的条件，因为浓盐酸一直在挥发，瓶子上标的浓度只是大概。"
                     "分析化学的办法是先按大概浓度配一瓶——量浓盐酸约 9 mL 稀释到 1 L，"
                     "得到约 0.1 mol/L——再用基准物质把浓度定准，这就是标定。"
                     "基准物质要够纯、够稳定、称得准：无水碳酸钠在 270～300 ℃ 烘至恒重后"
                     "不易吸潮也不变质（吸湿性小，但称量动作还是要快），"
                     "摩尔质量又大（105.99 g/mol）。摩尔质量大为什么是优点？"
                     "标一份要的碳酸钠的物质的量是固定的，摩尔质量越大、要称的克数就越多，"
                     "同一台天平那点绝对误差折成百分比就越小。"
                     "每种基准物各有代价：另一种常用的硼砂（带结晶水的硼酸钠）"
                     "摩尔质量更大，但必须放在控湿干燥器里保存，否则所含结晶水的量一变，"
                     "称出来的就不再是那个化合物。称样量定在 0.15～0.20 g、滴定体积要求 20 mL 以上，"
                     "是为了让天平和滴定管各自的误差都压在千分之一左右（详见「数字上的讲究」一节）。",
             "terms": [],
             "sources": ["src_textbook_exp3", "src_gb601", "src_guide_online", "src_guide_online_prep"]},
            {"section_id": "indicator", "title": "为什么用甲基橙判终点",
             "show_in": ["context"], "order": 3, "rung_id": "L4-indicator",
             "summary": "碳酸钠全部被中和时 pH 约 3.9，正好落在甲基橙由黄变橙的变色区里。",
             "body": "碳酸钠被盐酸中和要经过两个[化学计量点](term:equivalence_point)："
                     "碱被中和一半时约 pH 8.3，全部中和时约 pH 3.8～3.9。本实验要的是第二个，"
                     "它落在[滴定突跃](term:titration_jump)之内，也正好落进甲基橙的变色区"
                     "（pH 3.1～4.4，由黄变橙），所以选它做[指示剂](term:indicator)。"
                     "终点的手感是「黄色刚变成橙色就停」：橙色意味着刚踏进变色区，"
                     "再往深红滴就过了。近终点前还要加热煮沸赶走溶解的 CO₂。"
                     "CO₂ 溶进水生成的碳酸会抵抗 pH 变化（[缓冲](term:buffering)），"
                     "带来两个后果：一是颜色变得慢，突跃不再陡峭，近终点更要半滴半滴地加；"
                     "二是 pH 提前降进变色区，按「刚变橙就停」判，终点会落在计量点之前。"
                     "教材里还有甲基红与溴甲酚绿配成的混合指示剂，"
                     "两条变色带叠在一起，变色更锐，道理相同。",
             "terms": ["equivalence_point", "titration_jump", "indicator", "buffering"],
             "sources": ["src_textbook_exp3", "src_ac_book", "src_gb601_boil"]},
            {"section_id": "soda-ash", "title": "碱灰是什么，总碱度为什么折算成 Na₂O",
             "show_in": ["context"], "order": 4, "rung_id": None,
             "summary": "碱灰是工业碳酸钠；滴到全部碱被中和，各成分合计折算成 Na₂O 才好比较。",
             "body": "[碱灰](term:soda_ash)就是工业纯碱：主要成分 Na₂CO₃，还可能混少量 NaOH、"
                     "NaHCO₃ 和不与酸反应的盐类。滴到甲基橙变橙那一刻，所有碱性成分都被中和完了，"
                     "所以测得的不是某一种成分，而是「总」碱度。行业口径把它统一折算成 Na₂O 的"
                     "质量分数：不管混的是什么碱，都按「相当于多少氧化钠」报告，"
                     "不同批次、不同厂家的碱灰才能直接比大小。试样先在 270～300 ℃ 烘干，"
                     "一举两得：赶走吸附的水，也把 NaHCO₃ 转成 Na₂CO₃。工业样混得不匀，"
                     "所以称约 2 g 溶解后定容到 250 mL，每次移取 25.00 mL 来滴，"
                     "取三份[平行测定](term:parallel_determination)。",
             "terms": ["soda_ash", "parallel_determination"],
             "sources": ["src_textbook_exp3", "src_guide_online"]},
            {"section_id": "precision", "title": "平行、偏差与数字上的讲究",
             "show_in": ["context"], "order": 5, "rung_id": "L5-mass-range",
             "summary": "称样与体积的下限不是拍脑袋，是让天平和滴定管各占约千分之一的误差。",
             "body": "同一份试样独立测三份，叫平行测定；三份不会完全一样，散得多开用"
                     "[相对平均偏差](term:relative_average_deviation)衡量。教学要求标定与平行测定的"
                     "相对平均偏差都在 0.2% 以内；更严格的标定规程要求三次结果的平均偏差不超过 0.1%；"
                     "工业纯碱因为混得不匀，允差放宽到各次相对偏差 ±0.5%。这些数不是拍脑袋："
                     "天平两次称量共 ±0.0002 g、滴定管两次读数共 ±0.02 mL，"
                     "称样 0.15～0.20 g、滴定体积 20 mL 以上，各自恰好把误差压到千分之一左右。"
                     "如果实测偏差明显超出这个预算，问题多半不在仪器而在操作，"
                     "比如各份终点颜色判断不一致。",
             "terms": ["relative_average_deviation"],
             "sources": ["src_textbook_exp3", "src_ac_book", "src_guide_online_dev"]},
            {"section_id": "thinking", "title": "思考题里的逻辑链：这个实验真正考什么",
             "show_in": ["context"], "order": 6, "rung_id": "L5-error-type",
             "summary": "基准物吸水会一路把浓度和总碱度都推高；这就是系统误差同向传递的样板。",
             "body": "两条最值得会推的链。第一条（思考题 2）：基准物吸了水，称出的 0.15 g 里"
                     "真正的碳酸钠变少，滴定时消耗的盐酸跟着变少，而计算时仍按 0.15 g 纯品算——"
                     "于是盐酸浓度被算高；再用这支「偏浓」的盐酸去滴碱灰，总碱度也跟着偏高。"
                     "误差每一步同向传递、三份一起偏高，这就是[系统误差](term:systematic_error)的样板。"
                     "第二条（思考题 3、实验 4）：想知道碱灰里除 Na₂CO₃ 外混的是 NaOH 还是 NaHCO₃，"
                     "先加酚酞滴到红色褪去、再加甲基橙滴到变橙，比较两段体积的关系就能判断组成——"
                     "这叫双指示剂法，正好能回答「总碱度偏高是不是因为含 NaOH」。",
             "terms": ["systematic_error"],
             "sources": ["src_textbook_exp3"]},
            {"section_id": "read-curve", "title": "怎么读教材里的滴定曲线",
             "show_in": ["literature"], "order": 2, "rung_id": None,
             "summary": "横轴是滴入的酸量，纵轴是 pH；先找那段近乎竖直的跳变，计量点藏在中间。",
             "body": "教材里的滴定曲线，横轴是滴入的 HCl 体积（或滴定分数——即滴入体积除以"
                     "计量点体积，用来消掉浓度差异），纵轴是 pH——溶液酸碱强弱的数值。"
                     "读它先找三样东西。第一，起点：碳酸钠溶液本身是碱性的，pH 在 10 以上。"
                     "第二，[滴定突跃](term:titration_jump)——计量点附近多加一滴酸、"
                     "pH 就大幅下坠的那段近乎竖直的陡壁，[化学计量点](term:equivalence_point)"
                     "（本实验约 pH 3.9）就藏在陡壁中间。第三，曲线有两个台阶而不是一个："
                     "第一个小台阶（约 pH 8.3）是碱被中和了一半的瞬间，不是终点。"
                     "学生的数据不是一条曲线，是三个孤立的点——三份各自滴到变色那一下的体积；"
                     "把它们放到曲线的横轴上，就是在回答「我的终点落在陡壁的哪个位置」。",
             "terms": ["titration_jump", "equivalence_point"],
             "sources": ["src_ac_book", "src_textbook_exp3"]},
            {"section_id": "why-compare", "title": "为什么要拿文献曲线和自己的终点比",
             "show_in": ["literature"], "order": 3, "rung_id": None,
             "summary": "浓度不同比不了数字，换成滴定分数后比的是「终点落没落在突跃段里」。",
             "body": "03 页要把教材（或论文）里的滴定曲线和学生自己的三个终点画到一张图上。"
                     "麻烦在于：文献用的盐酸浓度、称样量都和学生不同，同样 25 mL，含义完全不一样。"
                     "所以 M4 先把双方换算到同一个坐标——滴入体积除以各自的计量点体积，"
                     "得到滴定分数，1.0 就是刚好反应完的位置。换算后，终点落在文献曲线的"
                     "突跃段之内，说明终点判断合理；落在突跃边缘之外，就要回头怀疑终点颜色判断"
                     "或 CO₂ 干扰。这是「拿参照对比判断自己」在曲线上的样子：不是比数字相等，"
                     "而是比位置合理。",
             "terms": [],
             "sources": ["src_docs", "src_ac_book"]},
        ],
    },
    "ladder": {                              # 讲解阶梯，规则见 docs/wiki.md#讲解阶梯
        "base_level": 3,
        "rungs": [
            {"rung_id": "L3-formula", "level": 3, "title": "浓度与总碱度怎么算",
             "concept": "浓度与总碱度都从称样量和滴定体积代公式算出；相对平均偏差——各次结果偏离平均值的平均幅度占平均值的百分比——衡量三份平行散得多开",
             "anchor": {"type": "fit"}, "trigger": None,
             "source": "实验教材 实验 3 数据处理"},
            {"rung_id": "L4-indicator", "level": 4, "title": "为什么用甲基橙",
             "concept": "碳酸钠被盐酸中和有两个化学计量点——碱被中和一半（约 pH 8.3）与全部中和（约 pH 3.9）两个理论瞬间——第二个落进甲基橙的变色区（pH 3.1～4.4），所以用它判终点",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "实验教材 实验目的 3；分析化学教材 酸碱滴定章"},
            {"rung_id": "L4-co2", "level": 4, "title": "为什么近终点要防 CO₂",
             "concept": "溶解的 CO₂ 生成的碳酸会抵抗 pH 变化（缓冲作用），带来两个后果：颜色变得慢、突跃不再陡峭；pH 提前降进变色区，按「刚变橙就停」判的终点落在计量点之前",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材；GB/T 601-2016 HCl 标定条（煮沸步骤，待核）"},
            {"rung_id": "L5-error-type", "level": 5, "title": "误差分系统与随机",
             "concept": "系统误差让三份结果朝同一方向歪、拉动平均值，随机误差让结果忽大忽小、拉大离散。基准物吸水 1% 会让浓度被算高、总碱度跟着偏高，是系统误差的样板（思考题 2）",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "实验教材 思考题 2"},
            {"rung_id": "L5-mass-range", "level": 5, "title": "为什么称样量 0.15～0.20 g、滴定体积 20 mL 以上",
             "concept": "称样 0.15～0.20 g 时天平两次称量 ±0.0002 g 约合千分之一，滴定体积 20 mL 以上时滴定管两次读数 ±0.02 mL 也约合千分之一——两头都不拖后腿",
             "anchor": {"type": "fit"}, "trigger": None,
             "source": "分析化学教材 误差与有效数字章"},
            {"rung_id": "L6-budget", "level": 6, "title": "测量不确定度",
             "concept": "把称量、读数、定容、移液各自的误差贡献合成一个扩展不确定度——真值大概率落在其中的范围——用来判断偏差是否超出仪器所能解释",
             "anchor": {"type": "comparison", "target": "error_budget"}, "trigger": None,
             "source": "JJF 1059.1-2012（GUM 国内版）"},
            {"rung_id": "L6-endpoint-error", "level": 6, "title": "指示剂终点误差可以定量算",
             "concept": "终点误差可用林邦误差公式定量算出：本实验不煮沸时甲基橙在计量点前约 0.15 mL 就开始变色，煮沸后变色点移到计量点后约 0.02 mL",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材 终点误差节"},
            {"rung_id": "L7-gb601", "level": 7, "title": "标准方法怎么保证可靠",
             "concept": "国家标准 GB/T 601 对标定的平行份数、人员比对与重复性限都有明文要求，比教学上的 0.2% 严格——按标准做，结果才跨实验室可比",
             "anchor": {"type": "qc", "rule_id": "standardization_rpad"},
             "trigger": {"qc_fail": "standardization_rpad"},
             "source": "GB/T 601-2016（具体份数与限值待核）"},
            {"rung_id": "L7-next-dual-indicator", "level": 7, "title": "下一步：双指示剂法",
             "concept": "先酚酞后甲基橙分两段滴（双指示剂法），区分碱灰混的是 NaOH 还是 NaHCO₃（思考题 3、实验 4），检验总碱度偏高是否因含 NaOH",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "实验教材 实验 4"},
            {"rung_id": "L8-potentiometric", "level": 8, "title": "不用指示剂判终点",
             "concept": "电位滴定——用 pH 计代替人眼找突跃——加上 Gran 作图，不用指示剂也能定终点",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材 电位滴定章"},
            {"rung_id": "L9-ocean-alkalinity", "level": 9, "title": "科研里的同一件事",
             "concept": "海水总碱度——海水中所有能中和酸的成分总量——用开放式电位滴定测定，是海洋碳循环研究的基础量；本实验测的就是同一类量",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "Dickson et al., Guide to Best Practices for Ocean CO₂ Measurements（PICES 3, 2007）, SOP 3b"},
        ],
    },
    "variables": {
        "columns": [
            {"key": "m", "role": "mass", "unit": "g"},                       # 标定行：基准 Na₂CO₃ 质量
            {"key": "V", "role": "volume", "unit": "mL"},                    # 标定/测定行：HCl 滴定体积
            {"key": "ms", "role": "sample_mass", "unit": "g", "optional": True},  # 测定行：碱灰试样质量
        ]
    },
    "reference": {
        "datasets": [],
        "crm": None,
        "limits": [{"label": "纯 Na₂CO₃ 理论总碱度（以 Na₂O 计）", "value": 58.47,
                    "unit": "%", "operator": "<="}],
    },
    "qc_rules": [
        {"rule_id": "standardization_rpad", "params": {"max": 0.002},
         "citation": "GB/T 601-2016 / 分析化学实验教学要求（相对平均偏差 ≤0.2%）"},
        {"rule_id": "parallel_rpd", "params": {"max": 0.002},
         "citation": "分析化学实验平行测定要求（相对平均偏差 ≤0.2%）"},
        {"rule_id": "outlier_grubbs", "params": {"alpha": 0.05}, "citation": "GB/T 4883"},
    ],
}

IODINE_TEMPLATE = {
    "schema_version": CONTRACT_VERSION,
    "name": "碘钟反应动力学（过硫酸根-碘离子，规划中）",
    "purpose": "改变温度测变色时间，ln(1/t) 对 1/T 求 Arrhenius 活化能",
    "model": "arrhenius",
    "model_params": {},
    "variables": {
        "columns": [
            {"key": "T", "role": "temperature", "unit": "°C"},
            {"key": "t", "role": "time", "unit": "s"},
        ]
    },
    "reference": {"datasets": [], "crm": None, "limits": []},
    "qc_rules": [
        {"rule_id": "calibration_r2", "params": {"min": 0.99}, "citation": "教学惯例"},
        {"rule_id": "outlier_grubbs", "params": {"alpha": 0.05}, "citation": "GB/T 4883"},
    ],
}

TEMPLATES = {
    "tpl_alkali_titration": {"status": "演示", "template": ALKALI_TITRATION_TEMPLATE},
    "tpl_iodine_clock": {"status": "规划", "template": IODINE_TEMPLATE},
}


class CreateContext(BaseModel):
    template_id: str


def _all_templates(request: Request) -> list[tuple[str, dict]]:
    """内置模板 + 模板库（组织知识层，见 docs/wiki.md）。内置优先，库中 id 不得与内置冲突。"""
    items = [{"status": meta["status"], "template": dict(meta["template"], id=tid)}
             for tid, meta in TEMPLATES.items()]
    items += [{"status": t.get("status", "自定义"), "template": t}
              for t in request.app.state.store.list_templates()
              if t.get("id") and t["id"] not in TEMPLATES]
    return items


@router.get("/templates")
def list_templates(request: Request):
    out = []
    for item in _all_templates(request):
        t = item["template"]
        m = REGISTRY[t["model"]]
        out.append({
            "id": t["id"],
            "name": t["name"],
            "model": t["model"],
            "required_roles": [m.x_role, m.y_role],
            "formula": m.formula,
            "reference_preview": {
                "n_datasets": len(t.get("reference", {}).get("datasets", [])),
                "crm": t.get("reference", {}).get("crm"),
                "limits": t.get("reference", {}).get("limits", []),
            },
            "has_guide": bool(t.get("guide")),   # 0.8.0：模板库列表标「有导读」
            "status": item["status"],
        })
    return out


@router.post("/templates", status_code=201)
def create_template(request: Request, body: dict):
    """把一次实验的骨架沉淀为可复用模板（wiki 层）。模板不含 datasets。"""
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST", "message": "模板需要是 JSON 对象", "detail": {}}})
    name = str(body.get("name") or "").strip()
    model_id = body.get("model")
    if not name or model_id not in REGISTRY:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST",
                      "message": f"模板需要非空 name 与注册表内的 model（{sorted(REGISTRY)}）",
                      "detail": {}}})
    m = REGISTRY[model_id]
    columns = (body.get("variables") or {}).get("columns") or []
    roles = {c.get("role") for c in columns if isinstance(c, dict)}
    if not {m.x_role, m.y_role} <= roles:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST",
                      "message": f"variables.columns 缺少必需角色: {m.x_role}/{m.y_role}",
                      "detail": {}}})

    store = request.app.state.store
    tpl = copy.deepcopy(body)
    tpl.pop("datasets", None)
    tpl["id"] = tpl.get("id") or new_id("tpl")
    if tpl["id"] in TEMPLATES or store.get_template(tpl["id"]) is not None:
        return JSONResponse(status_code=409, content={
            "error": {"code": "CONFLICT", "message": f"模板 id 已存在: {tpl['id']}", "detail": {}}})
    tpl["schema_version"] = CONTRACT_VERSION
    tpl["status"] = "自定义"
    tpl.setdefault("model_params", {})
    tpl.setdefault("purpose", "")
    tpl.setdefault("reference", {"datasets": [], "crm": None, "limits": []})
    tpl.setdefault("qc_rules", [])
    return store.put_template(tpl)


@router.post("/contexts", status_code=201)
def create_context(body: CreateContext, request: Request):
    item = next((it for it in _all_templates(request)
                 if it["template"]["id"] == body.template_id), None)
    if item is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"模板不存在: {body.template_id}", "detail": {}}})
    ctx = copy.deepcopy(item["template"])
    ctx.pop("status", None)
    ctx["id"] = new_id("ctx")
    ctx["datasets"] = {"mine": None}
    return request.app.state.store.put_context(ctx)


@router.get("/contexts/{id}")
def get_context(id: str, request: Request):
    ctx = request.app.state.store.get_context(id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {id}", "detail": {}}})
    return ctx


@router.put("/contexts/{id}")
def put_context(id: str, request: Request, body: dict):
    if not isinstance(body, dict) or "model" not in body:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST", "message": "ExperimentContext 需要 model", "detail": {}}})
    body = copy.deepcopy(body)
    body["id"] = id
    return request.app.state.store.put_context(body)
