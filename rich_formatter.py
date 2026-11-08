# --- START OF FILE rich_formatter.py ---

import re
import html

CODEVER = "v2.0 | rich_formatter (Telegram Native Rich)"

LANG_MAP = {
    "js": "javascript", "javascript": "javascript", "mjs": "javascript", "cjs": "javascript",
    "ts": "typescript", "typescript": "typescript",
    "py": "python", "python": "python",
    "html": "html", "xml": "xml", "css": "css", "scss": "scss",
    "kt": "kotlin", "kotlin": "kotlin", "java": "java",
    "cpp": "cpp", "c": "c", "cs": "csharp", "csharp": "csharp",
    "go": "go", "rust": "rust", "rs": "rust",
    "php": "php", "sql": "sql", "sh": "bash", "bash": "bash",
    "json": "json", "yaml": "yaml", "yml": "yaml", "md": "markdown"
}

DIVIDER_LINE = "━━━━━━━━━━━━━━━━━━"


def auto_detect_language(code: str) -> str:
    sample = (code or "")[:500]
    if re.search(r"^\s*(<!DOCTYPE|<html|<div|<head|<body)", sample, re.I): return "html"
    if re.search(r'^\s*(\{|\[)\s*[\r\n]', sample, re.M) and re.search(r'"[^"]+"\s*:', sample, re.M): return "json"
    if re.search(r"^\s*(import\s|from\s.*import|def\s|class\s.*:|print\(|elif\s)", sample, re.M): return "python"
    if re.search(r"^\s*(const\s|let\s|var\s|function\s|export\s|console\.log|import\s.*from)", sample, re.M): return "javascript"
    if re.search(r"^\s*(SELECT\s|INSERT\s|UPDATE\s|DELETE\s|CREATE\s+TABLE)", sample, re.I): return "sql"
    if re.search(r"^\s*(#!/bin/|curl\s|npm\s|pip\s|docker\s|git\s)", sample, re.M): return "bash"
    return "text"


def get_default_filename(lang: str, idx: int) -> str:
    ext_map = {
        "html": "index.html", "css": "style.css", "javascript": "script.js",
        "typescript": "app.ts", "python": "main.py", "sql": "query.sql",
        "bash": "run.sh", "json": "data.json"
    }
    return ext_map.get(lang, f"code_{idx}.txt")


def normalize_code_blocks(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n")

    text = re.sub(
        r"```[a-z0-9_-]*\s*\n*(?:FILE|ФАЙЛ):\s*`?([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+)`?\s*\n*```",
        r"FILE: \1\n", text, flags=re.I
    )

    unfenced_file_regex = re.compile(
        r"((?:FILE|ФАЙЛ|файл|File):\s*`?([a-zA-Z0-9_.-]+\.([a-zA-Z0-9]+))`?)\s*\n+(?!```)([\s\S]+?)(?=(?:\n(?:FILE|ФАЙЛ|файл|File):|\n\n[А-ЯA-Z][а-яa-z\s]{5,}:|$))",
        re.I
    )

    def _replace_unfenced(m):
        header = m.group(1)
        ext = m.group(3).lower()
        code = m.group(4).strip()
        if not code:
            return m.group(0)
        lang = LANG_MAP.get(ext, ext)
        return f"{header}\n```{lang}\n{code}\n```\n\n"

    text = unfenced_file_regex.sub(_replace_unfenced, text)

    if text.count("```") % 2 != 0:
        text += "\n```"

    return text


def format_inline(text: str) -> str:
    if not text:
        return ""
    s = html.escape(text)

    # 1. LaTeX формулы -> в моноширинный код
    s = re.sub(r"\$([^\$\n]+)\$", r"<code>\1</code>", s)
    # 2. Спойлеры
    s = re.sub(r"\|\|([\s\S]+?)\|\|", r"<tg-spoiler>\1</tg-spoiler>", s)
    # 3. Маркеры ==текст== -> жирное подчеркивание <b><u>текст</u></b>
    s = re.sub(r"==([^=\n]+)==", r"<b><u>\1</u></b>", s)
    # 4. Зачеркивание
    s = re.sub(r"~~([\s\S]+?)~~", r"<s>\1</s>", s)
    # 5. Жирный и курсив
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"__([^_]+)__", r"<b>\1</b>", s)
    s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
    s = re.sub(r"(?:^|\s)_([^_]+)_(?:$|\s|[.,!?:])", r" <i>\1</i> ", s)
    # 6. Моноширинный инлайн-код
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    # 7. Ссылки
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2">\1</a>', s)

    return s.strip()


def format_to_rich_html(raw_input: str) -> str:
    """Преобразует Rich Markdown в 100% валидный для Telegram HTML."""
    if not raw_input:
        return ""
    text = normalize_code_blocks(raw_input).strip()

    protected_blocks = []

    def make_token(pfx: str, idx: int) -> str:
        return f"___TG_BLOCK_{pfx}_{idx}___"

    # 1. Блоки кода с указанием имени файла
    code_idx = 0
    code_pattern = re.compile(
        r"(?:(?:FILE|ФАЙЛ|файл|File):\s*`?([a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+)`?\s*\n+)?```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```",
        re.I
    )

    def _replace_code(m):
        nonlocal code_idx
        explicit_fn = m.group(1)
        raw_lang = (m.group(2) or "").strip().lower()
        code_body = m.group(3).strip()
        if not code_body:
            return ""

        lang = LANG_MAP.get(raw_lang, auto_detect_language(code_body))
        safe_code = html.escape(code_body)
        lang_attr = f' class="language-{lang}"' if lang else ""
        fn = explicit_fn.strip() if explicit_fn else get_default_filename(lang, code_idx + 1)

        token = make_token("CODE", code_idx)
        code_idx += 1

        block_html = (
            f"📄 <b>{html.escape(fn)}</b>\n"
            f"<pre><code{lang_attr}>{safe_code}</code></pre>"
        )
        protected_blocks.append({"token": token, "html": block_html})
        return f"\n\n{token}\n\n"

    text = code_pattern.sub(_replace_code, text)

    # 2. Блочные формулы LaTeX
    math_idx = 0
    def _replace_math(m):
        nonlocal math_idx
        token = make_token("MATH", math_idx)
        math_idx += 1
        expr = html.escape(m.group(1).strip())
        protected_blocks.append({"token": token, "html": f"<pre><code>{expr}</code></pre>"})
        return f"\n\n{token}\n\n"

    text = re.sub(r"\$\$([\s\S]+?)\$\$", _replace_math, text)

    # 3. Цитаты -> в нативный <blockquote>
    quote_idx = 0
    quote_pattern = re.compile(r"((?:^[ \t]*>[^\n]+\r?\n?)+)", re.M)
    def _replace_quote(m):
        nonlocal quote_idx
        raw_q = m.group(1).splitlines()
        clean_lines = [re.sub(r"^[ \t]*>[ \t]?", "", l).strip() for l in raw_q if l.strip()]
        if not clean_lines:
            return m.group(0)
        token = make_token("QUOTE", quote_idx)
        quote_idx += 1
        inner = "\n".join(format_inline(l) for l in clean_lines)
        protected_blocks.append({"token": token, "html": f"<blockquote expandable>{inner}</blockquote>"})
        return f"\n\n{token}\n\n"

    text = quote_pattern.sub(_replace_quote, text)

    # 4. Горизонтальные разделители ---
    def _replace_hr(m):
        token = make_token("HR", len(protected_blocks))
        protected_blocks.append({"token": token, "html": DIVIDER_LINE})
        return f"\n\n{token}\n\n"

    text = re.sub(r"^[ \t]*(?:---|\*\*\*|___)[ \t]*$", _replace_hr, text, flags=re.M)

    # 5. Заголовки # ... ######
    def _replace_headings(m):
        title = m.group(2).strip()
        token = make_token("HEAD", len(protected_blocks))
        protected_blocks.append({"token": token, "html": f"<b>{format_inline(title)}</b>"})
        return f"\n\n{token}\n\n"

    text = re.sub(r"^(#{1,6})\s+(.+)$", _replace_headings, text, flags=re.M)

    # 6. Списки -> в красивые маркеры с буллетами •
    list_idx = 0
    list_pattern = re.compile(r"((?:^[ \t]*(?:[-*•+]|\d+\.)[ \t]+[^\n]+\r?\n?)+)", re.M)
    def _replace_list(m):
        nonlocal list_idx
        raw_items = m.group(1).splitlines()
        clean_items = [l.strip() for l in raw_items if l.strip()]
        if not clean_items:
            return m.group(0)
        lines_out = []
        for it in clean_items:
            content = re.sub(r"^(?:[-*•+]|\d+\.)[ \t]+", "", it)
            lines_out.append(f"• {format_inline(content)}")
        token = make_token("LIST", list_idx)
        list_idx += 1
        protected_blocks.append({"token": token, "html": "\n".join(lines_out)})
        return f"\n\n{token}\n\n"

    text = list_pattern.sub(_replace_list, text)

    # 7. Сборка абзацев (разделяем двойным переносом строки)
    paragraphs = text.split("\n\n")
    final_chunks = []

    for p in paragraphs:
        clean = p.strip()
        if not clean:
            continue

        matched = next((b for b in protected_blocks if b["token"] == clean), None)
        if matched:
            final_chunks.append(matched["html"])
            continue

        if "___TG_BLOCK_" in clean:
            lines = clean.splitlines()
            buf = []
            for l in lines:
                l_strip = l.strip()
                f_blk = next((b for b in protected_blocks if b["token"] == l_strip), None)
                if f_blk:
                    if buf:
                        final_chunks.append(format_inline(" ".join(buf)))
                        buf = []
                    final_chunks.append(f_blk["html"])
                elif l_strip:
                    buf.append(l_strip)
            if buf:
                final_chunks.append(format_inline(" ".join(buf)))
            continue

        final_chunks.append(format_inline(clean))

    result = "\n\n".join(final_chunks).strip()

    # Убираем дублирование разделителей
    result = re.sub(rf"(?:{DIVIDER_LINE}\s*){{2,}}", f"{DIVIDER_LINE}\n\n", result)

    # Обрамляем карточку в фирменную рамку-разделитель (как у Пупса)
    if not result.startswith(DIVIDER_LINE):
        result = f"{DIVIDER_LINE}\n\n{result}"
    if not result.endswith(DIVIDER_LINE):
        result = f"{result}\n\n{DIVIDER_LINE}"

    return result


def sanitize_to_standard_html(rich_html: str) -> str:
    """Гарантирует отсутствие любых неподдерживаемых тегов."""
    if not rich_html:
        return ""
    s = rich_html
    # Удаляем любые теги кроме строго разрешенных Telegram:
    # b, strong, i, em, u, ins, s, strike, del, tg-spoiler, a, code, pre, blockquote
    allowed_tags = r"(/?(?:b|strong|i|em|u|ins|s|strike|del|tg-spoiler|a|code|pre|blockquote)(?:\s+[^>]*)?>)"
    
    # Временно помечаем разрешенные теги
    tokens = []
    def _stash(m):
        tokens.append(m.group(0))
        return f"__VALID_TAG_{len(tokens)-1}__"

    s = re.sub(allowed_tags, _stash, s, flags=re.I)
    # Все остальные теги удаляем
    s = re.sub(r"<[^>]+>", "", s)
    # Возвращаем разрешенные
    for idx, tag in enumerate(tokens):
        s = s.replace(f"__VALID_TAG_{idx}__", tag)

    return s.strip()