# Translation Rules for Linux Kernel Chinese Documentation

Reference: <https://docs.kernel.org/translations/zh_CN/how-to.html>

## Line Width

- Each line must not exceed **80 display columns**.
- A CJK (Chinese/Japanese/Korean) character counts as **2 display columns**.
- An ASCII character counts as **1 display column**.
- Example: 40 Chinese characters = 80 display columns (the maximum).

To verify line widths programmatically:

```python
import unicodedata, sys
for i, line in enumerate(open(sys.argv[1]), 1):
    w = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1
            for c in line.rstrip('\n'))
    if w > 80:
        print(f'  Line {i}: width {w}')
```

## RST Format Requirements

### Title Underlines

- One ASCII character in the title corresponds to **one** underline symbol.
- One CJK character in the title corresponds to **two** underline symbols.

### Preserve These Elements

The following must be kept in their original English form, untranslated:

- Code blocks (`.. code-block::`) and command-line examples
- All RST directives (`.. note::`, `.. warning::`, `.. tip::`, etc.)
- Cross-reference labels inside `:ref:` and `:doc:` directives
- File paths, command names, function names, and variable names

## Terminology Rules

### Glossary

Use the project glossary (`config/glossary.txt`) as the authoritative
terminology reference.

### First Occurrence Format

When a technical term appears for the first time in a document, write the
Chinese translation followed by the English original in parentheses:

```
内存屏障（memory barrier）
```

### No-Translate Terms

Certain terms are marked as "do not translate" in the glossary. These must
remain in English. Common examples:

- CPU, DMA, IRQ, MMIO, SoC
- API, ABI
- Git, Makefile

### Code Identifiers

Function names, variable names, struct names, and file paths are always kept
in their original English form, regardless of surrounding text.

## Punctuation Rules

### Chinese Punctuation

Use Chinese (full-width) punctuation in translated prose:

| Type        | Use this | Not this |
|-------------|----------|----------|
| Comma       | ，       | ,        |
| Period      | 。       | .        |
| Semicolon   | ；       | ;        |
| Colon       | ：       | :        |
| Quotes      | ""       | ""       |
| Parentheses | （）     | ()       |

### English Punctuation

English (half-width) punctuation is used **only** inside code blocks,
inline code, and command examples.

### CJK-ASCII Spacing

When Chinese text is mixed with English words or numbers, insert **one space**
between CJK and ASCII characters:

```
使用 CPU 进行计算
支持 DMA 传输
共有 128 个条目
```

## File Header

Every translation file must begin with the following header. Reference:
<https://docs.kernel.org/translations/zh_CN/how-to.html>

```rst
.. SPDX-License-Identifier: GPL-2.0
.. include:: ../disclaimer-zh_CN.rst

:Original: Documentation/<path-to-english-file>

:翻译:

 <Name> <<email>>
```

### Header Rules

- The `SPDX` line and `.. include::` line must be adjacent with **no blank
  line** between them.
- Use `:翻译:` (Chinese), **not** `:Translator:`.
- A blank line separates the `.. include::` line from `:Original:`.
- A blank line separates `:Original:` from `:翻译:`.
- The translator name is indented by one space.

## What to Preserve (Summary)

| Element                  | Translate? | Example                           |
|--------------------------|------------|-----------------------------------|
| Prose / paragraphs       | Yes        | --                                |
| Code blocks              | No         | `.. code-block:: c`               |
| Command examples         | No         | `make menuconfig`                 |
| RST directives           | No         | `.. warning::`                    |
| Cross-reference labels   | No         | `:ref:\`label\``                  |
| File paths               | No         | `Documentation/admin-guide/`      |
| Function / variable names| No         | `kmalloc()`, `nr_pages`           |
| Glossary no-translate    | No         | CPU, DMA, IRQ                     |
| Title text               | Yes        | --                                |
| Title underline symbols  | Adjust     | Match display width of title      |

## Common Issues

### checkpatch Line-Length Warnings

`checkpatch.pl` may report lines as too long because it counts CJK characters
as single bytes. If a line is within 80 display columns (using the 2-column
CJK rule), the warning can be safely acknowledged. Reflow the line if it
genuinely exceeds the limit.

### RST Build Failures

Common causes:

- Title underline not long enough (remember: 2 symbols per CJK character).
- Inconsistent indentation.
- Missing blank lines between paragraphs.
- Incorrect reference labels.
