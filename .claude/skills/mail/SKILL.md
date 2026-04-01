---
name: mail
description: Search and view kernel mailing list threads on lore.kernel.org
allowed-tools: Bash, Read, WebFetch
argument-hint: "[--search [query]] [--thread <url>] [--replies <url>] [--reply <url>] [--local --search <query>] [--local --thread <message-id>]"
---

# 邮件列表查看与回复

在 lore.kernel.org 上搜索、查看内核邮件列表的线程，以及起草回复。不调用外部脚本。

> **路径约定**：Bash cwd 可能被污染，**不可假设为项目根目录**。
> 项目根目录（`<ROOT>`）从 skill 的 Base directory 推导：`Base directory` 往上 3 级。
> 每条 Bash 命令用 `cd <ROOT>/linux && ...` 或 `cd <ROOT> && ...` 显式切换。

解析 `$ARGUMENTS`：提取 `--search [query]`、`--thread <id|url>`、`--replies <id|url>`、`--reply <id|url>`。

## Message-ID 提取

对于 `--thread`、`--replies`、`--reply` 模式，从用户输入中提取 bare message-id：
- 输入 `https://lore.kernel.org/linux-doc/MSG-ID/` → `MSG-ID`
- 输入 `<MSG-ID>` → `MSG-ID`
- 输入 `MSG-ID` → `MSG-ID`

---

## 模式 1：`--search [query]` — 搜索邮件

### 无 query 时

获取默认搜索关键词：

```bash
cd <ROOT>/linux && git config user.email
```

用 `f:<email>` 作为 query。

### 执行搜索

构建 lore.kernel.org Atom feed URL：

```bash
python3 -c "import urllib.parse; print(urllib.parse.quote('<query>'))"
```

用 `WebFetch` 获取 Atom feed：

```
WebFetch(url="https://lore.kernel.org/linux-doc/?q=<encoded_query>&x=A", prompt="Extract all entries from this Atom feed. For each entry, return: title, author name, updated date, and link href. Also note if the title starts with 'Re:' (mark as reply).")
```

用中文汇报搜索结果：编号列表，每条包含标题、作者、日期、URL，回复标记 `[reply]`。

---

## 模式 2：`--thread <id|url>` — 查看完整线程

### 下载 mbox

WebFetch 不支持 gzip binary，使用 curl：

```bash
curl -s -A "kernel-translations-agent/1.0" -f "https://lore.kernel.org/linux-doc/<message-id>/t.mbox.gz" | gunzip > /tmp/_kt_thread.mbox
```

### 解析 mbox

```bash
python3 -c "
import mailbox, email, email.header, sys

def decode_header(value):
    if value is None: return '(none)'
    parts = email.header.decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ' '.join(result)

def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace')
        return '(no plain text body)'
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or 'utf-8'
        return payload.decode(charset, errors='replace')
    return '(empty body)'

mbox = mailbox.mbox('/tmp/_kt_thread.mbox')
messages = list(mbox)
for i, msg in enumerate(messages):
    marker = 'REPLY' if msg.get('In-Reply-To') else 'ORIGINAL'
    print(f'={'*72}')
    print(f'[{marker}] Message {i+1}/{len(messages)}')
    print(f'  From:    {decode_header(msg[\"From\"])}')
    print(f'  Subject: {decode_header(msg[\"Subject\"])}')
    print(f'  Date:    {msg[\"Date\"]}')
    print(f'  ID:      {msg[\"Message-ID\"]}')
    reply_to = msg.get('In-Reply-To', '')
    if reply_to: print(f'  Re:      {reply_to}')
    print(f'{'-'*72}')
    body = get_body(msg).rstrip()
    lines = body.split('\n')
    if len(lines) > 200:
        print('\n'.join(lines[:200]))
        print(f'\n... ({len(lines)-200} more lines truncated)')
    else:
        print(body)
    print()
print(f'Thread contains {len(messages)} message(s).')
"
```

用中文总结线程内容。

---

## 模式 3：`--replies <id|url>` — 只看回复

同 `--thread` 模式，但 Python 解析时跳过第一条消息（`start = 1`）：

修改上面的 Python 脚本，在循环前加 `messages = messages[1:]`。

如果线程只有原始消息没有回复，告知用户。

用中文总结审核意见。

---

## 模式 4：`--reply <id|url>` — 起草回复（Claude 处理）

这个模式由 Claude 自行处理，不调用脚本：

1. 先用上面 `--thread` 的方式获取完整线程内容
2. 用中文总结审核者的意见和建议
3. 根据审核意见，用英文起草回复邮件：
   - 使用 bottom-posting 风格（引用原文在上，回复在下）
   - 逐条回应审核意见
   - 语气礼貌专业
   - 如果涉及代码修改，说明会在 v2/vN 补丁中修复
4. 将起草的回复展示给用户确认

---

## 模式 5：`--local` — 本地邮件操作

使用 mbsync + notmuch 操作本地邮件，替代 lore.kernel.org 远程查询。

### 前置检查

```bash
which notmuch mbsync 2>&1
```

如不可用，提示用户安装并配置 mbsync + notmuch。

### `--local --search <query>` — 本地搜索

先同步邮件：

```bash
mbsync -a 2>&1 | tail -5
```

```bash
notmuch new 2>&1
```

执行搜索：

```bash
notmuch search '<query>' 2>&1
```

用中文汇报搜索结果：编号列表，每条包含线程 ID、主题、日期、匹配数。

### `--local --thread <message-id>` — 本地查看线程

先同步邮件：

```bash
mbsync -a 2>&1 | tail -5
```

```bash
notmuch new 2>&1
```

查找包含指定 message-id 的线程：

```bash
notmuch search "id:<message-id>" 2>&1
```

获取完整线程内容：

```bash
notmuch show --format=json "thread:{id:<message-id>}" 2>&1 | python3 -c "
import json, sys
data = json.load(sys.stdin)
def walk(msgs, depth=0):
    for msg in msgs:
        if isinstance(msg, list):
            walk(msg, depth)
        elif isinstance(msg, dict):
            hdrs = msg.get('headers', {})
            body_parts = msg.get('body', [])
            body_text = ''
            for part in body_parts:
                if part.get('content-type','').startswith('text/plain'):
                    body_text = part.get('content', '')
                elif 'content' in part and isinstance(part['content'], list):
                    for sub in part['content']:
                        if isinstance(sub, dict) and sub.get('content-type','').startswith('text/plain'):
                            body_text = sub.get('content', '')
            marker = 'REPLY' if hdrs.get('In-Reply-To') else 'ORIGINAL'
            print(f'={'*'*72}')
            print(f'[{marker}]')
            print(f'  From:    {hdrs.get(\"From\", \"?\")}')
            print(f'  Subject: {hdrs.get(\"Subject\", \"?\")}')
            print(f'  Date:    {hdrs.get(\"Date\", \"?\")}')
            print(f'  ID:      {hdrs.get(\"Message-ID\", \"?\")}')
            irt = hdrs.get('In-Reply-To', '')
            if irt: print(f'  Re:      {irt}')
            print(f'{'-'*72}')
            lines = body_text.rstrip().split('\n')
            if len(lines) > 200:
                print('\n'.join(lines[:200]))
                print(f'\n... ({len(lines)-200} more lines truncated)')
            else:
                print(body_text.rstrip())
            print()
walk(data)
"
```

用中文总结线程内容。

## 注意事项

- 所有对用户的汇报使用中文
- 起草的回复邮件使用英文（内核社区通用语言）
- 如果搜索/获取失败，提示用户检查网络连接或 URL 是否正确
- 临时文件用完后清理：`rm -f /tmp/_kt_thread.mbox`
- `--local` 模式使用本地 notmuch 数据库，速度更快且不依赖网络
