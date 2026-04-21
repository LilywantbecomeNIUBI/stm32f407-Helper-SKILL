# Textbook Excerpts

Use this file to turn textbook lookup into chapter plus page-level guidance.

## Goal

Make `search_materials.py` return:
- textbook chapter
- source PDF
- page range
- key pages
- short excerpt or reading note

## Recommended Layout

```text
materials/
└── textbook/
    ├── stm32f4-guide.pdf
    ├── stm32f4-guide.index.json
    └── ...
```

The `.index.json` file is the page-level index used by the skill. You do not need to finish the whole book at once. Start with high-frequency contest chapters such as USART, TIM, ADC/DMA, OLED, and EXTI.

## Manifest Schema

```json
{
  "book_id": "alientek-stm32f4-hal",
  "source_pdf": "stm32f4-guide.pdf",
  "category": ["adc", "dma", "usart"],
  "entries": [
    {
      "id": "book_adc_excerpt",
      "book_id": "book_adc",
      "chapter": "第三十一章 ADC 实验",
      "category": ["adc", "dma"],
      "keywords": ["adc", "dma", "连续采样", "采样时间"],
      "summary": "这一章适合确认 ADC + DMA 的触发方式、通道配置和缓冲区处理顺序。",
      "excerpt": "先确认 ADC 通道和采样时间，再确认 DMA 是否工作在循环模式；如果使用定时器触发，要同时检查触发源和更新频率。",
      "page_range": "421-436",
      "key_pages": [423, 426, 431]
    }
  ]
}
```

Notes:
- `book_id` should match the chapter `id` in [book_catalog.json](/D:/活动/比赛/电赛/嵌入式skill/stm32f407-Helper/assets/book_catalog.json:1) when possible.
- `source_pdf` is relative to `materials/textbook/`.
- `excerpt` should stay short. It is a reading note, not a copied chapter.
- `key_pages` uses integer page numbers.

## Build Command

After writing one or more `*.index.json` files under `materials/textbook/`, run:

```bash
python scripts/generate_book_excerpt_catalog.py --materials-root "<materials_root>"
```

That generates:

```text
assets/book_excerpt_catalog.json
```

## Usage Rules

- Use `book_catalog.json` to locate the chapter first.
- If `book_excerpt_catalog.json` has a match, return the page range, key pages, and excerpt.
- If no excerpt index exists, say that only chapter-level location is available.
- Do not invent page numbers or excerpts.
