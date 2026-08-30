"""标准PDF模板生成脚本。

PDF是导出产物不是可编辑源，规范要求在源文件层整改后重新导出。本脚本即该源文件，
修改模板必须改本脚本再运行，不得直接编辑PDF。

程序化入口：build(output_path, font_sources=...)
"""

import os
from pathlib import Path
from typing import Mapping

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# 朱墨方案token。切换方案时只改本块，取值见 references/theme-style.md
T = {
    "SERIES_MAIN": "#C8102E",
    "SERIES_MAIN_DEEP": "#9E0B24",
    "SERIES_BENCH": "#2A6FB0",
    "SERIES_BENCH_DEEP": "#174A7C",
    "SERIES_ACCENT": "#D99A2B",
    "SERIES_DEFENSE": "#1F8A5B",
    "INK": "#1E1B18",
    "TEXT_SECONDARY": "#5A5148",
    "MUTED": "#8C8073",
    "GRID_LINE": "#EBE3D6",
    "PANEL": "#FFFFFF",
    "RULE_BLACK": "#000000",
    "UP_TONE": "#C8102E",
    "DOWN_TONE": "#1F8A5B",
}
C = {k: HexColor(v) for k, v in T.items()}

# 字体解析链只覆盖常见系统位置；调用方可通过font_sources显式提供字体文件。
# 中文一律宋体，标题用宋体加粗区分层级，不允许静默回落到任意系统字体。
FONT_CHAIN = {
    "CN_TITLE": [
        ("SongtiSCBold", "/System/Library/Fonts/Supplemental/Songti.ttc", 1),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc", 0),
    ],
    "CN_BODY": [
        ("SongtiSC", "/System/Library/Fonts/Supplemental/Songti.ttc", 6),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc", 0),
    ],
    "CN_BOLD": [
        ("SongtiSCBold", "/System/Library/Fonts/Supplemental/Songti.ttc", 1),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc", 0),
    ],
    "EN_BODY": [
        (
            "TimesNewRoman",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
            None,
        ),
        ("TimesNewRoman", "C:/Windows/Fonts/times.ttf", None),
        (
            "TimesNewRoman",
            "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf",
            None,
        ),
    ],
    "EN_BOLD": [
        (
            "TimesNewRomanBold",
            "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
            None,
        ),
        ("TimesNewRomanBold", "C:/Windows/Fonts/timesbd.ttf", None),
        (
            "TimesNewRomanBold",
            "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
            None,
        ),
    ],
    "NUM": [
        ("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf", None),
        ("Arial", "C:/Windows/Fonts/arial.ttf", None),
        ("Arial", "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", None),
    ],
}

F = {}
PW, PH = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 22 * mm, 20 * mm, 18 * mm


def register_fonts(
    font_sources: Mapping[str, tuple[str, str | Path, int | None]] | None = None,
):
    """Register required fonts from explicit sources or known system locations.

    ``font_sources`` maps every role in ``FONT_CHAIN`` to
    ``(registered_name, font_path, subfont_index)``. Supplying only part of the
    mapping is allowed; remaining roles use the discovery chain.
    """
    resolved = {}
    for role, chain in FONT_CHAIN.items():
        candidates = (
            [font_sources[role]] if font_sources and role in font_sources else chain
        )
        for cand in candidates:
            name, path, idx = cand
            path = os.fspath(path)
            if not os.path.isfile(path):
                continue
            try:
                pdfmetrics.registerFont(
                    TTFont(name, path, subfontIndex=idx)
                    if idx is not None
                    else TTFont(name, path)
                )
            except Exception:
                continue
            resolved[role] = name
            break
        else:
            raise RuntimeError(
                "找不到字体角色%s。请通过font_sources显式提供字体文件，不能静默替换。"
                % role
            )
    return resolved


def styles():
    return {
        "h1": ParagraphStyle(
            "h1",
            fontName=F["CN_TITLE"],
            fontSize=16,
            leading=24,
            textColor=C["INK"],
            spaceBefore=10,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=F["CN_TITLE"],
            fontSize=13,
            leading=20,
            textColor=C["INK"],
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=F["CN_BODY"],
            fontSize=10.5,
            leading=18,
            textColor=C["INK"],
            firstLineIndent=21,
            spaceAfter=4,
        ),
        "cap": ParagraphStyle(
            "cap",
            fontName=F["CN_BODY"],
            fontSize=9,
            leading=14,
            textColor=C["MUTED"],
            alignment=TA_CENTER,
            spaceBefore=4,
        ),
        "note": ParagraphStyle(
            "note",
            fontName=F["CN_BODY"],
            fontSize=8.5,
            leading=13,
            textColor=C["MUTED"],
            alignment=TA_LEFT,
            spaceBefore=3,
        ),
        "eq": ParagraphStyle(
            "eq",
            fontName=F["EN_BODY"],
            fontSize=11,
            leading=20,
            textColor=C["INK"],
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=6,
        ),
        "title": ParagraphStyle(
            "title",
            fontName=F["CN_TITLE"],
            fontSize=22,
            leading=32,
            textColor=C["INK"],
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
    }


def three_line_table(data, col_widths, head_rows=1, group_rows=()):
    """黑色三线表。顶线和底线1.5磅，表头下线0.75磅，分组线0.5磅，无竖线无正文行横线。"""
    t = Table(data, colWidths=col_widths, repeatRows=head_rows, hAlign="CENTER")
    cmds = [
        ("FONTNAME", (0, 0), (-1, head_rows - 1), F["CN_BOLD"]),
        ("FONTNAME", (0, head_rows), (-1, -1), F["CN_BODY"]),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), C["INK"]),
        ("TEXTCOLOR", (0, head_rows), (0, -1), C["TEXT_SECONDARY"]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, C["RULE_BLACK"]),
        ("LINEBELOW", (0, head_rows - 1), (-1, head_rows - 1), 0.75, C["RULE_BLACK"]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, C["RULE_BLACK"]),
    ]
    for r in group_rows:
        cmds.append(("LINEABOVE", (0, r), (-1, r), 0.5, C["RULE_BLACK"]))
    t.setStyle(TableStyle(cmds))
    return t


def frame_deco(canvas, doc):
    canvas.saveState()
    canvas.setFont(F["CN_BODY"], 8.5)
    canvas.setFillColor(C["MUTED"])
    canvas.drawString(MARGIN_X, PH - MARGIN_TOP + 6 * mm, "标准格式PDF报告模板")
    canvas.drawRightString(PW - MARGIN_X, PH - MARGIN_TOP + 6 * mm, "研究部")
    canvas.setStrokeColor(C["GRID_LINE"])
    canvas.setLineWidth(0.5)
    canvas.line(
        MARGIN_X, PH - MARGIN_TOP + 4 * mm, PW - MARGIN_X, PH - MARGIN_TOP + 4 * mm
    )
    canvas.line(MARGIN_X, MARGIN_BOT - 4 * mm, PW - MARGIN_X, MARGIN_BOT - 4 * mm)
    canvas.setFont(F["NUM"], 8.5)
    canvas.drawCentredString(PW / 2, MARGIN_BOT - 9 * mm, str(doc.page))
    canvas.setFont(F["CN_BODY"], 8)
    canvas.drawString(MARGIN_X, MARGIN_BOT - 9 * mm, "数据来源：按实际填写")
    canvas.restoreState()


def build(
    out: str | Path = "standard-pdf-template.pdf",
    *,
    font_sources: Mapping[str, tuple[str, str | Path, int | None]] | None = None,
    overwrite: bool = False,
):
    output_path = Path(out).expanduser().resolve()
    if output_path.exists() and not overwrite:
        raise FileExistsError("输出已存在，默认不覆盖: %s" % output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    F.clear()
    F.update(register_fonts(font_sources))
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT,
        title="标准格式PDF报告模板",
        author="研究部",
    )
    frame = Frame(
        MARGIN_X, MARGIN_BOT, PW - 2 * MARGIN_X, PH - MARGIN_TOP - MARGIN_BOT, id="main"
    )
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=frame_deco)])
    s = styles()
    w = PW - 2 * MARGIN_X
    story = [
        Paragraph("标准格式PDF报告模板", s["title"]),
        Spacer(1, 4 * mm),
        Paragraph("1. 研究结论", s["h1"]),
        Paragraph(
            "正文使用宋体10.5磅，行距18磅，首行缩进2字符。结论先写判断再写依据，"
            "不堆砌背景。数字精度按统一规则保留，百分比1位小数，比率2位小数。",
            s["body"],
        ),
        Paragraph("1.1 组合表现", s["h2"]),
        Paragraph(
            "表格使用黑色三线表，顶线和底线1.5磅，表头下线0.75磅，不画竖线，"
            "正文行之间不画横线，表头无底色仅加粗。",
            s["body"],
        ),
        Spacer(1, 3 * mm),
        Paragraph("表1-1 组合表现指标", s["cap"]),
        three_line_table(
            [
                [
                    "组合",
                    "期末净值",
                    "年化收益",
                    "年化波动",
                    "最大回撤",
                    "夏普",
                    "卡玛",
                ],
                ["策略组合", "1.000", "0.0%", "0.0%", "0.0%", "0.00", "0.00"],
                ["基准组合", "1.000", "0.0%", "0.0%", "0.0%", "0.00", "0.00"],
                ["超额", "0.000", "0.0%", "0.0%", "0.0%", "0.00", "0.00"],
            ],
            [w * 0.19] + [w * 0.135] * 6,
            head_rows=1,
            group_rows=(3,),
        ),
        Paragraph(
            "注：口径为区间年化，样本区间按实际填写。数据来源：按实际填写。", s["note"]
        ),
        Spacer(1, 5 * mm),
        Paragraph("1.2 图表占位", s["h2"]),
        Paragraph(
            "图表必须可搜索可复制，不得整表截图。图表编号与正文引用一致，引用写见图1-1。",
            s["body"],
        ),
        Paragraph("图1-1 净值与回撤", s["cap"]),
        Spacer(1, 3 * mm),
        Paragraph("2. 方法与公式", s["h1"]),
        Paragraph(
            "公式必须使用数学排版，不得使用代码字体或截图。变量在首次出现时定义，"
            "同一变量不得在不同章节表示不同含义。",
            s["body"],
        ),
        KeepTogether(
            [
                Paragraph(
                    "IR = IC&#772; / &#963;(IC) &#215; &#8730;N &#160;&#160;&#160;&#160;(2-1)",
                    s["eq"],
                ),
                Paragraph(
                    "其中IC为期间信息系数均值，&#963;(IC)为其标准差，N为年化调仓次数。",
                    s["body"],
                ),
            ]
        ),
        Spacer(1, 4 * mm),
        Paragraph("2.1 参数设置", s["h2"]),
        Paragraph("表2-1 主要参数", s["cap"]),
        three_line_table(
            [
                ["参数", "取值", "口径", "来源"],
                ["回看窗口", "60", "交易日", "设定"],
                ["调仓频率", "20", "交易日", "设定"],
                ["交易成本", "0.10%", "单边", "设定"],
            ],
            [w * 0.24, w * 0.18, w * 0.24, w * 0.34],
        ),
        Paragraph("注：参数变动需同步更新敏感性分析。", s["note"]),
    ]
    doc.build(story)
    return output_path
