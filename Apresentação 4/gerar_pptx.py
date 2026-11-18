# -*- coding: utf-8 -*-
"""Gera PPTX a partir do briefing relatorio_balancos_doe.html"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import nsmap
from pptx.oxml import parse_xml
from lxml import etree
import copy

# Cores do briefing
INK = RGBColor(0x0F, 0x1C, 0x2E)
INK_SOFT = RGBColor(0x2A, 0x3D, 0x55)
PAPER = RGBColor(0xF3, 0xEF, 0xE6)
ACCENT = RGBColor(0x0D, 0x6E, 0x6E)
ACCENT2 = RGBColor(0xC4, 0x5C, 0x26)
WHITE = RGBColor(0xFF, 0xFC, 0xF6)
CARD = RGBColor(0xFF, 0xFC, 0xF6)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank = prs.slide_layouts[6]


def set_run(run, size=14, bold=False, color=INK, font="Calibri"):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def add_bg(slide, color=PAPER):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    # send to back
    spTree = slide.shapes._spTree
    sp = shape._element
    spTree.remove(sp)
    spTree.insert(2, sp)
    return shape


def add_rect(slide, left, top, width, height, fill=CARD, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.color.rgb = RGBColor(0xD0, 0xC8, 0xB8)
        shape.line.width = Pt(0.75)
    else:
        shape.line.fill.background()
    shape.adjustments[0] = 0.08
    return shape


def add_text(slide, left, top, width, height, text, size=14, bold=False,
             color=INK, align=PP_ALIGN.LEFT, font="Calibri", anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    try:
        tf._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])
    except Exception:
        pass
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_run(run, size=size, bold=bold, color=color, font=font)
    return box


def add_paras(slide, left, top, width, height, lines, size=13, color=INK_SOFT, bold_first=False, spacing=6):
    """lines: list of str or (str, bold)"""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(lines):
        if isinstance(item, tuple):
            text, is_bold = item
        else:
            text, is_bold = item, (bold_first and i == 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(spacing)
        run = p.add_run()
        run.text = text
        set_run(run, size=size, bold=is_bold, color=color if not is_bold else INK)
    return box


def add_bullet_list(slide, left, top, width, height, items, size=13, color=INK_SOFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(8)
        p.level = 0
        run = p.add_run()
        run.text = "•  " + item
        set_run(run, size=size, bold=False, color=color)
    return box


def accent_bar(slide, left, top, width, height=Inches(0.08), color=ACCENT):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    return s


def section_title(slide, title, subtitle=None):
    add_text(slide, Inches(0.6), Inches(0.35), Inches(12), Inches(0.55),
             title, size=28, bold=True, color=INK, font="Georgia")
    accent_bar(slide, Inches(0.6), Inches(0.95), Inches(1.2))
    if subtitle:
        add_text(slide, Inches(0.6), Inches(1.1), Inches(12), Inches(0.55),
                 subtitle, size=14, color=INK_SOFT)


def pill(slide, left, top, text, warm=False):
    w = Inches(0.12 * len(text) + 0.35)
    h = Inches(0.28)
    fill = RGBColor(0xE8, 0xD5, 0xC8) if warm else RGBColor(0xD4, 0xE8, 0xE8)
    c = ACCENT2 if warm else ACCENT
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.adjustments[0] = 0.5
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    set_run(run, size=10, bold=True, color=c)
    try:
        tf._txBody.bodyPr.set("anchor", "ctr")
    except Exception:
        pass
    return shape


def footer(slide, page, total=12):
    add_text(slide, Inches(0.6), Inches(7.1), Inches(10), Inches(0.3),
             "Briefing de investimento · Diagramação e publicação legal · DOE/SP · 30/07/2026",
             size=9, color=INK_SOFT)
    add_text(slide, Inches(11.8), Inches(7.1), Inches(1), Inches(0.3),
             f"{page}/{total}", size=9, color=INK_SOFT, align=PP_ALIGN.RIGHT)


# ─── SLIDE 1: Capa ───────────────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s, PAPER)
# left accent strip
strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.25), SLIDE_H)
strip.fill.solid()
strip.fill.fore_color.rgb = ACCENT
strip.line.fill.background()

add_text(s, Inches(0.7), Inches(1.6), Inches(11), Inches(0.4),
         "BRIEFING DE INVESTIMENTO  ·  PRODUTO DE PUBLICAÇÃO LEGAL",
         size=12, bold=True, color=ACCENT)
add_text(s, Inches(0.7), Inches(2.15), Inches(11.5), Inches(1.6),
         "Quebrar o monopólio das agências\nde publicidade legal",
         size=36, bold=True, color=INK, font="Georgia")
add_text(s, Inches(0.7), Inches(4.0), Inches(11), Inches(1.0),
         "Ferramenta de diagramação e preparação de balanços e demais matérias — "
         "alternativa às agências, com arquivo pronto para o Diário Oficial "
         "ou jornal de grande circulação.",
         size=16, color=INK_SOFT)

# meta row
metas = [
    ("Evidência", "DOE/SP · Empresarial"),
    ("Recortes", "2020–2021 e 2025–jul/2026"),
    ("Atualizado", "30/07/2026"),
]
for i, (lab, val) in enumerate(metas):
    x = Inches(0.7 + i * 3.8)
    add_text(s, x, Inches(5.4), Inches(3.5), Inches(0.25), lab, size=10, bold=True, color=ACCENT)
    add_text(s, x, Inches(5.65), Inches(3.5), Inches(0.3), val, size=13, color=INK)

footer(s, 1)


# ─── SLIDE 2: Agenda ─────────────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Agenda")
items = [
    ("01", "Oportunidade", "Por que este projeto existe"),
    ("02", "Problema", "O “monopólio” das agências de publicidade legal"),
    ("03", "Público-alvo", "S/As, adjacências e demanda observada"),
    ("04", "Volumetria", "DOE/SP — legado e digital"),
    ("05", "Concorrência", "Agências, canais e posicionamento"),
    ("06", "Solução", "Jornada do cliente e prioridades de MVP"),
    ("07", "Decisão", "Perguntas e próximo passo"),
]
for i, (num, title, desc) in enumerate(items):
    row, col = divmod(i, 2)
    x = Inches(0.6 + col * 6.3)
    y = Inches(1.5 + row * 1.15)
    add_rect(s, x, y, Inches(5.9), Inches(1.0))
    add_text(s, x + Inches(0.25), y + Inches(0.2), Inches(0.7), Inches(0.5),
             num, size=22, bold=True, color=ACCENT, font="Georgia")
    add_text(s, x + Inches(1.1), y + Inches(0.18), Inches(4.5), Inches(0.35),
             title, size=16, bold=True, color=INK)
    add_text(s, x + Inches(1.1), y + Inches(0.52), Inches(4.5), Inches(0.35),
             desc, size=12, color=INK_SOFT)
footer(s, 2)


# ─── SLIDE 3: Oportunidade ───────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(
    s, "Por que este projeto existe",
    "Empresas obrigadas a publicar balanços dependem das agências. A proposta é industrializar a diagramação e devolver autonomia ao cliente."
)
cards = [
    ("Dor do mercado", False, "Complexidade = barreira",
     "Critérios técnicos e jurídicos das publicações em jornal de grande circulação elevam o custo de erro e empurram a demanda para agências especializadas."),
    ("Hipótese de produto", True, "Arquivo pronto + escolha do canal",
     "Receber dados → gerar matéria diagramada → cliente publica no DOE ou encaminha ao jornal preferido, sem depender da agência."),
    ("Papel deste levantamento", False, "Volumetria e sazonalidade",
     "Usar publicações reais no caderno Empresarial do DOE/SP como proxy de demanda recorrente (quem publica, quando e com que tipo)."),
]
for i, (pill_t, warm, title, body) in enumerate(cards):
    x = Inches(0.5 + i * 4.2)
    add_rect(s, x, Inches(2.0), Inches(4.0), Inches(4.2))
    pill(s, x + Inches(0.25), Inches(2.25), pill_t, warm=warm)
    add_text(s, x + Inches(0.25), Inches(2.75), Inches(3.5), Inches(0.7),
             title, size=16, bold=True, color=INK)
    add_text(s, x + Inches(0.25), Inches(3.5), Inches(3.5), Inches(2.4),
             body, size=13, color=INK_SOFT)
footer(s, 3)


# ─── SLIDE 4: Problema ───────────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(
    s, "O “monopólio” das agências de publicidade legal",
    "Não é monopólio legal formal: é domínio de mercado pela especialização."
)
# two columns
add_rect(s, Inches(0.5), Inches(1.9), Inches(5.9), Inches(3.6))
add_text(s, Inches(0.75), Inches(2.1), Inches(5.4), Inches(0.4),
         "O que as agências controlam hoje", size=16, bold=True, color=INK)
add_bullet_list(s, Inches(0.75), Inches(2.6), Inches(5.4), Inches(2.6), [
    "Interpretação dos critérios de diagramação e veiculação",
    "Relacionamento com jornais de grande circulação",
    "Fluxo de comprovantes e prazos perante a obrigação societária",
    "Pacote “faz por você” — da matéria à publicação",
], size=13)

add_rect(s, Inches(6.7), Inches(1.9), Inches(5.9), Inches(3.6))
add_text(s, Inches(6.95), Inches(2.1), Inches(5.4), Inches(0.4),
         "Onde há espaço para concorrer", size=16, bold=True, color=INK)
add_bullet_list(s, Inches(6.95), Inches(2.6), Inches(5.4), Inches(2.6), [
    "Automatizar a geração do arquivo publicável (core técnico)",
    "Separar produção da matéria de compra de mídia",
    "Oferecer DOE e jornal como opções de canal, não como amarra",
    "Atender volume sazonal (AGO / balanços) com escala digital",
], size=13)

# tese
callout = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(5.7), Inches(12.1), Inches(1.0))
callout.fill.solid()
callout.fill.fore_color.rgb = RGBColor(0xF5, 0xE6, 0xDC)
callout.line.fill.background()
callout.adjustments[0] = 0.06
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.7), Inches(0.12), Inches(1.0))
bar.fill.solid()
bar.fill.fore_color.rgb = ACCENT2
bar.line.fill.background()
add_text(s, Inches(0.85), Inches(5.85), Inches(11.5), Inches(0.7),
         "Tese competitiva: se a complexidade da diagramação deixar de ser um obstáculo, "
         "a agência deixa de ser inevitável — e passa a ser uma escolha (ou um canal opcional).",
         size=13, color=INK)
footer(s, 4)


# ─── SLIDE 5: Público-alvo ───────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(
    s, "Público-alvo da solução",
    "Núcleo: empresas com obrigação legal de publicar demonstrações e atos — em especial sociedades anônimas."
)
pubs = [
    ("Núcleo jurídico", "S/As",
     "Obrigação típica de publicação de demonstrações (Lei 6.404 e alterações), com regras atuais de jornal / modelo híbrido / Central de Balanços conforme porte e tipo."),
    ("Adjacências", "Ltdas e OS",
     "Nem toda Ltda tem obrigação de jornal; ainda assim há volume relevante de entidades (fundações, OS, holdings) publicando no Empresarial."),
    ("Demanda observada", "Recorrente",
     "Publicações anuais concentradas em fev–jun; base instalada que se repete ciclo a ciclo (AGO / balanços)."),
]
for i, (lab, val, hint) in enumerate(pubs):
    x = Inches(0.5 + i * 4.2)
    add_rect(s, x, Inches(2.0), Inches(4.0), Inches(4.2))
    add_text(s, x + Inches(0.3), Inches(2.3), Inches(3.4), Inches(0.3),
             lab.upper(), size=11, bold=True, color=INK_SOFT)
    add_text(s, x + Inches(0.3), Inches(2.8), Inches(3.4), Inches(0.7),
             val, size=28, bold=True, color=ACCENT, font="Georgia")
    add_text(s, x + Inches(0.3), Inches(3.7), Inches(3.4), Inches(2.2),
             hint, size=13, color=INK_SOFT)
footer(s, 5)


# ─── SLIDE 6: Volumetria KPIs ────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(
    s, "Volumetria observada no DOE/SP",
    "Proxy de mercado em São Paulo: caderno Empresarial — legado (2020–2021) e digital (2025–jul/2026)."
)
kpis = [
    ("Pubs 2020–2021", "4.446", "Sumários do acervo legado · Empresarial"),
    ("Empresas distintas 2020–21", "3.384", "Base ampla no período de pico"),
    ("Pubs 2025–jul/2026", "496", "API digital · Atos Empresariais"),
    ("Empresas distintas 2025–26", "285", "Até 30/07/2026 · ciclo ainda aberto"),
]
for i, (lab, val, hint) in enumerate(kpis):
    x = Inches(0.45 + i * 3.2)
    add_rect(s, x, Inches(2.0), Inches(3.05), Inches(2.8))
    add_text(s, x + Inches(0.2), Inches(2.2), Inches(2.65), Inches(0.4),
             lab.upper(), size=10, bold=True, color=INK_SOFT)
    add_text(s, x + Inches(0.2), Inches(2.7), Inches(2.65), Inches(0.8),
             val, size=36, bold=True, color=ACCENT if i < 2 else ACCENT2, font="Georgia")
    add_text(s, x + Inches(0.2), Inches(3.7), Inches(2.65), Inches(0.8),
             hint, size=12, color=INK_SOFT)

callout = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(5.2), Inches(12.1), Inches(1.4))
callout.fill.solid()
callout.fill.fore_color.rgb = RGBColor(0xDC, 0xEB, 0xEB)
callout.line.fill.background()
callout.adjustments[0] = 0.06
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.2), Inches(0.12), Inches(1.4))
bar.fill.solid()
bar.fill.fore_color.rgb = ACCENT
bar.line.fill.background()
add_text(s, Inches(0.85), Inches(5.4), Inches(11.5), Inches(1.0),
         "Leitura para investimento: mesmo com métodos diferentes entre legado e digital, "
         "a demanda é recorrente, sazonal e composta por milhares de entidades no ciclo. "
         "Isso sustenta um produto de produção de matéria — não apenas um serviço pontual.\n"
         "Obs.: números de 2020–21 e 2025–26 usam métodos distintos e não devem ser lidos como série histórica única.",
         size=13, color=INK)
footer(s, 6)


# ─── SLIDE 7: Sazonalidade ───────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Sazonalidade — picos de carga",
              "Concentração em fev–jun; abril é o mês de maior volume nos dois recortes.")

# Legado picos
add_rect(s, Inches(0.5), Inches(1.85), Inches(6.0), Inches(4.7))
add_text(s, Inches(0.75), Inches(2.05), Inches(5.5), Inches(0.35),
         "Picos 2020–2021 (legado)", size=15, bold=True, color=INK)
legado_picos = [("2021-04", 928, 1.0), ("2020-04", 637, 0.69), ("2020-06", 551, 0.59),
                ("2021-05", 479, 0.52), ("2021-03", 466, 0.50)]
for i, (mes, val, pct) in enumerate(legado_picos):
    y = Inches(2.55 + i * 0.7)
    add_text(s, Inches(0.75), y, Inches(1.3), Inches(0.35), mes, size=12, color=INK)
    track = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.1), y + Inches(0.08), Inches(3.2), Inches(0.22))
    track.fill.solid()
    track.fill.fore_color.rgb = RGBColor(0xE0, 0xD8, 0xCC)
    track.line.fill.background()
    track.adjustments[0] = 0.5
    fill_c = ACCENT2 if i == 0 else ACCENT
    bar_w = Inches(3.2 * pct)
    fill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.1), y + Inches(0.08), bar_w, Inches(0.22))
    fill.fill.solid()
    fill.fill.fore_color.rgb = fill_c
    fill.line.fill.background()
    fill.adjustments[0] = 0.5
    add_text(s, Inches(5.4), y, Inches(0.9), Inches(0.35), f"{val:,}".replace(",", "."), size=12, bold=True, color=INK)

# Digital picos
add_rect(s, Inches(6.7), Inches(1.85), Inches(6.0), Inches(4.7))
add_text(s, Inches(6.95), Inches(2.05), Inches(5.5), Inches(0.35),
         "Picos 2025–2026 (digital)", size=15, bold=True, color=INK)
dig_picos = [("2026-04", 122, 1.0), ("2025-04", 116, 0.95), ("2025-03", 65, 0.53),
             ("2026-03", 52, 0.43), ("2025-05", 30, 0.25)]
for i, (mes, val, pct) in enumerate(dig_picos):
    y = Inches(2.55 + i * 0.7)
    add_text(s, Inches(6.95), y, Inches(1.3), Inches(0.35), mes, size=12, color=INK)
    track = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), y + Inches(0.08), Inches(3.2), Inches(0.22))
    track.fill.solid()
    track.fill.fore_color.rgb = RGBColor(0xE0, 0xD8, 0xCC)
    track.line.fill.background()
    track.adjustments[0] = 0.5
    fill_c = ACCENT2 if i == 0 else ACCENT
    bar_w = Inches(3.2 * pct)
    fill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), y + Inches(0.08), bar_w, Inches(0.22))
    fill.fill.solid()
    fill.fill.fore_color.rgb = fill_c
    fill.line.fill.background()
    fill.adjustments[0] = 0.5
    add_text(s, Inches(11.6), y, Inches(0.8), Inches(0.35), str(val), size=12, bold=True, color=INK)
footer(s, 7)


# ─── SLIDE 8: Tipos de matéria ───────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Tipos de matéria — família de títulos",
              "A ferramenta precisa cobrir a família de títulos, não um único template.")

# Legado familias
add_rect(s, Inches(0.5), Inches(1.85), Inches(6.0), Inches(4.5))
add_text(s, Inches(0.75), Inches(2.05), Inches(5.5), Inches(0.35),
         "Legado 2020–2021", size=15, bold=True, color=INK)
legado_fam = [("BALANÇO", 4397, 0.99), ("DEMONSTRAÇÕES FINANCEIRAS", 32, 0.15),
              ("DEMONSTRAÇÕES CONTÁBEIS", 14, 0.10), ("BALANÇO PATRIMONIAL", 3, 0.05)]
for i, (nome, val, pct) in enumerate(legado_fam):
    y = Inches(2.6 + i * 0.8)
    add_text(s, Inches(0.75), y, Inches(4.0), Inches(0.3), nome, size=12, bold=True, color=INK)
    add_text(s, Inches(4.8), y, Inches(1.4), Inches(0.3), f"{val:,}".replace(",", "."), size=12, bold=True, color=ACCENT, align=PP_ALIGN.RIGHT)
    track = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), y + Inches(0.35), Inches(5.4), Inches(0.18))
    track.fill.solid()
    track.fill.fore_color.rgb = RGBColor(0xE0, 0xD8, 0xCC)
    track.line.fill.background()
    track.adjustments[0] = 0.5
    fill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), y + Inches(0.35), Inches(5.4 * pct), Inches(0.18))
    fill.fill.solid()
    fill.fill.fore_color.rgb = ACCENT
    fill.line.fill.background()
    fill.adjustments[0] = 0.5

# Digital familias
add_rect(s, Inches(6.7), Inches(1.85), Inches(6.0), Inches(4.5))
add_text(s, Inches(6.95), Inches(2.05), Inches(5.5), Inches(0.35),
         "Digital 2025–2026", size=15, bold=True, color=INK)
dig_fam = [("DEMONSTRAÇÕES FINANCEIRAS", 192, 1.0), ("BALANÇO", 152, 0.79),
           ("BALANÇO PATRIMONIAL", 114, 0.59), ("DEMONSTRAÇÕES CONTÁBEIS", 38, 0.20)]
colors_f = [ACCENT, ACCENT2, INK_SOFT, RGBColor(0x8A, 0xA3, 0x9A)]
for i, (nome, val, pct) in enumerate(dig_fam):
    y = Inches(2.6 + i * 0.8)
    add_text(s, Inches(6.95), y, Inches(4.0), Inches(0.3), nome, size=12, bold=True, color=INK)
    add_text(s, Inches(11.0), y, Inches(1.4), Inches(0.3), str(val), size=12, bold=True, color=colors_f[i], align=PP_ALIGN.RIGHT)
    track = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.95), y + Inches(0.35), Inches(5.4), Inches(0.18))
    track.fill.solid()
    track.fill.fore_color.rgb = RGBColor(0xE0, 0xD8, 0xCC)
    track.line.fill.background()
    track.adjustments[0] = 0.5
    fill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.95), y + Inches(0.35), Inches(5.4 * pct), Inches(0.18))
    fill.fill.solid()
    fill.fill.fore_color.rgb = colors_f[i]
    fill.line.fill.background()
    fill.adjustments[0] = 0.5
footer(s, 8)


# ─── SLIDE 9: Concorrência ───────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Mercado e concorrência",
              "O campo competitivo não é só “outro software”: é o ecossistema que captura a jornada completa.")

add_rect(s, Inches(0.5), Inches(1.85), Inches(6.0), Inches(3.5))
pill(s, Inches(0.75), Inches(2.05), "Concorrentes atuais", warm=True)
add_text(s, Inches(0.75), Inches(2.5), Inches(5.5), Inches(0.35),
         "Agências de publicidade legal", size=16, bold=True, color=INK)
rows_a = [
    ("Posição", "Intermediário dominante"),
    ("Força", "Know-how + rede de jornais"),
    ("Fraqueza", "Custo, opacidade, dependência"),
    ("Ameaça ao status quo", "Self-service + arquivo pronto"),
]
for i, (k, v) in enumerate(rows_a):
    y = Inches(3.05 + i * 0.5)
    add_text(s, Inches(0.75), y, Inches(2.5), Inches(0.35), k, size=12, color=INK_SOFT)
    add_text(s, Inches(3.3), y, Inches(3.0), Inches(0.35), v, size=12, bold=True, color=INK, align=PP_ALIGN.RIGHT)

add_rect(s, Inches(6.7), Inches(1.85), Inches(6.0), Inches(3.5))
pill(s, Inches(6.95), Inches(2.05), "Canais de veiculação")
add_text(s, Inches(6.95), Inches(2.5), Inches(5.5), Inches(0.35),
         "DOE e jornais de grande circulação", size=16, bold=True, color=INK)
rows_b = [
    ("DOE/SP", "Canal oficial / digital"),
    ("Jornais", "Ainda exigidos em vários casos"),
    ("Central de Balanços", "Alternativa para perfil elegível"),
    ("Implicação", "Produto multi-canal"),
]
for i, (k, v) in enumerate(rows_b):
    y = Inches(3.05 + i * 0.5)
    add_text(s, Inches(6.95), y, Inches(2.5), Inches(0.35), k, size=12, color=INK_SOFT)
    add_text(s, Inches(9.5), y, Inches(3.0), Inches(0.35), v, size=12, bold=True, color=INK, align=PP_ALIGN.RIGHT)

add_rect(s, Inches(0.5), Inches(5.55), Inches(12.1), Inches(1.15))
add_text(s, Inches(0.75), Inches(5.7), Inches(11.6), Inches(0.3),
         "Posicionamento desejado", size=13, bold=True, color=ACCENT)
add_text(s, Inches(0.75), Inches(6.05), Inches(11.6), Inches(0.5),
         "Não substituir o jornal nem o DOE — substituir a necessidade de a agência diagramar e “empacotar” a matéria. "
         "O cliente mantém a escolha do veículo; nós entregamos conformidade de formato e velocidade.",
         size=13, color=INK_SOFT)
footer(s, 9)


# ─── SLIDE 10: Solução / jornada ─────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Solução proposta — jornada do cliente",
              "Fluxo-alvo da ferramenta de diagramação e publicação assistida.")

steps = [
    ("1. Entrada", "Empresa envia dados/demonstrações e metadados societários."),
    ("2. Regras", "Motor aplica critérios de diagramação e variantes de matéria."),
    ("3. Arquivo pronto", "Gera artefato publicável (layout validado para o canal)."),
    ("4. Escolha do canal", "Cliente opta por DOE ou jornal de grande circulação."),
    ("5. Encaminhamento", "Publica no DOE ou envia ao jornal — sem amarrar à agência."),
]
for i, (title, body) in enumerate(steps):
    x = Inches(0.35 + i * 2.6)
    add_rect(s, x, Inches(2.0), Inches(2.45), Inches(2.8))
    add_text(s, x + Inches(0.15), Inches(2.2), Inches(2.15), Inches(0.5),
             title.upper(), size=11, bold=True, color=ACCENT)
    add_text(s, x + Inches(0.15), Inches(2.85), Inches(2.15), Inches(1.6),
             body, size=12, color=INK_SOFT)
    if i < 4:
        # arrow hint
        add_text(s, x + Inches(2.3), Inches(3.1), Inches(0.35), Inches(0.4),
                 "→", size=18, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)

# MVP
add_text(s, Inches(0.5), Inches(5.1), Inches(12), Inches(0.35),
         "Prioridades do MVP (recomendação da volumetria)", size=14, bold=True, color=INK)
mvp = [
    "Templates de balanço / demonstrações — família de títulos mais frequente",
    "Capacidade sazonal (mar–mai) — pico em abril sem gargalo manual",
    "Exportação multi-canal — DOE e jornal; escolha fica com a empresa",
]
for i, t in enumerate(mvp):
    x = Inches(0.5 + i * 4.2)
    add_rect(s, x, Inches(5.55), Inches(4.0), Inches(1.15))
    add_text(s, x + Inches(0.2), Inches(5.7), Inches(3.6), Inches(0.85),
             t, size=12, color=INK_SOFT)
footer(s, 10)


# ─── SLIDE 11: Amostras ──────────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Amostras reais (proxy de clientes)",
              "Publicações observadas no caderno Empresarial do DOE/SP.")

# table legado
add_text(s, Inches(0.5), Inches(1.8), Inches(6), Inches(0.35),
         "2020–2021 (legado)", size=14, bold=True, color=ACCENT)
headers = ["Data", "Entidade", "Tipo"]
legado_rows = [
    ["2020-02-01", "BANCO SANTANDER (BRASIL) S.A", "BALANÇO"],
    ["2020-02-06", "BANCO DAYCOVAL S.A", "BALANÇO"],
    ["2020-02-07", "BANCO BRADESCO S.A", "BALANÇO"],
    ["2020-02-07", "KLABIN SA", "BALANÇO"],
    ["2020-02-08", "ALPARGATAS S.A", "BALANÇO"],
    ["2020-02-27", "AMBEV S.A", "BALANÇO"],
    ["2020-04-24", "DAE SA - ÁGUA E ESGOTO DE JUNDIAÍ", "BALANÇO"],
    ["2020-04-29", "BANCO FICSA S/A", "BALANÇO"],
]
# header row
y0 = Inches(2.2)
add_text(s, Inches(0.5), y0, Inches(1.4), Inches(0.3), "DATA", size=10, bold=True, color=INK_SOFT)
add_text(s, Inches(1.9), y0, Inches(3.5), Inches(0.3), "ENTIDADE", size=10, bold=True, color=INK_SOFT)
add_text(s, Inches(5.4), y0, Inches(1.2), Inches(0.3), "TIPO", size=10, bold=True, color=INK_SOFT)
for i, row in enumerate(legado_rows):
    y = Inches(2.5 + i * 0.45)
    add_text(s, Inches(0.5), y, Inches(1.4), Inches(0.35), row[0], size=11, color=INK_SOFT)
    add_text(s, Inches(1.9), y, Inches(3.5), Inches(0.35), row[1], size=11, color=INK)
    add_text(s, Inches(5.4), y, Inches(1.2), Inches(0.35), row[2], size=11, color=ACCENT)

# digital
add_text(s, Inches(6.9), Inches(1.8), Inches(6), Inches(0.35),
         "2025–2026 (digital)", size=14, bold=True, color=ACCENT2)
dig_rows = [
    ["2025-03-31", "CITIBANK, N.A. - FILIAL BRASILEIRA", "BALANÇOS PATRIMONIAIS"],
    ["2025-03-26", "SUSTENIDOS OS DE CULTURA", "DEM. CONTÁBEIS"],
    ["2025-04-14", "CPTM", "DEM. CONTÁBEIS"],
    ["2025-04-16", "CETESB", "BALANÇO"],
    ["2025-05-22", "SACYR CONSTRUCCION S.A.", "BP CONSOLIDADO"],
    ["2026-04-02", "CPP", "BALANÇO PATRIMONIAL"],
    ["2026-04-28", "FUNDAÇÃO BUTANTAN", "DEM. FINANCEIRAS"],
    ["2026-07-29", "SACYR CONSTRUCCION S.A.", "BP 31/12/2025"],
]
add_text(s, Inches(6.9), y0, Inches(1.4), Inches(0.3), "DATA", size=10, bold=True, color=INK_SOFT)
add_text(s, Inches(8.3), y0, Inches(3.2), Inches(0.3), "ENTIDADE", size=10, bold=True, color=INK_SOFT)
add_text(s, Inches(11.5), y0, Inches(1.5), Inches(0.3), "TIPO", size=10, bold=True, color=INK_SOFT)
for i, row in enumerate(dig_rows):
    y = Inches(2.5 + i * 0.45)
    add_text(s, Inches(6.9), y, Inches(1.4), Inches(0.35), row[0], size=11, color=INK_SOFT)
    add_text(s, Inches(8.3), y, Inches(3.2), Inches(0.35), row[1], size=11, color=INK)
    add_text(s, Inches(11.5), y, Inches(1.5), Inches(0.35), row[2], size=10, color=ACCENT2)
footer(s, 11)


# ─── SLIDE 12: Decisão ───────────────────────────────────────
s = prs.slides.add_slide(blank)
add_bg(s)
section_title(s, "Perguntas para a decisão de investimento",
              "Roteiro sugerido para a diretoria avaliar se e como avançar.")

qs = [
    ("Mercado", False, "Há demanda recorrente?",
     "Sim, no proxy DOE/SP: milhares de publicações no ciclo 2020–21 e centenas no digital recente, com sazonalidade clara."),
    ("Produto", True, "Onde está o wedge?",
     "Diagramação automática + arquivo pronto. A agência perde força quando a conformidade deixa de ser misteriosa."),
    ("Go-to-market", False, "Como entrar?",
     "Começar por balanços/DFs no pico AGO; depois expandir para demais matérias societárias e canais (DOE/jornal)."),
]
for i, (pill_t, warm, title, body) in enumerate(qs):
    x = Inches(0.5 + i * 4.2)
    add_rect(s, x, Inches(1.9), Inches(4.0), Inches(3.2))
    pill(s, x + Inches(0.25), Inches(2.15), pill_t, warm=warm)
    add_text(s, x + Inches(0.25), Inches(2.65), Inches(3.5), Inches(0.6),
             title, size=16, bold=True, color=INK)
    add_text(s, x + Inches(0.25), Inches(3.35), Inches(3.5), Inches(1.5),
             body, size=13, color=INK_SOFT)

callout = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(5.35), Inches(12.1), Inches(1.3))
callout.fill.solid()
callout.fill.fore_color.rgb = RGBColor(0xDC, 0xEB, 0xEB)
callout.line.fill.background()
callout.adjustments[0] = 0.06
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.35), Inches(0.12), Inches(1.3))
bar.fill.solid()
bar.fill.fore_color.rgb = ACCENT
bar.line.fill.background()
add_text(s, Inches(0.85), Inches(5.5), Inches(11.5), Inches(0.3),
         "Próximo passo sugerido", size=13, bold=True, color=ACCENT)
add_text(s, Inches(0.85), Inches(5.85), Inches(11.5), Inches(0.6),
         "Validar com 5–10 empresas publicantes (amostra do levantamento) se aceitariam gerar o arquivo na ferramenta "
         "e escolher o canal — medindo disposição a pagar versus o pacote da agência.",
         size=13, color=INK)
footer(s, 12)


out = r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\Apresentação 4\Briefing_Investimento_Publicacao_Legal.pptx"
prs.save(out)
print(f"Salvo: {out}")
print(f"Slides: {len(prs.slides)}")
