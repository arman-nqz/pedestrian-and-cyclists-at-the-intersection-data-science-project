"""Parse markdown tables from the V2 documents (read-only) so pages show the authoritative text, not a copy."""
import re, html
def tables(path):
    out, cur = [], []
    for line in open(path, encoding='utf-8'):
        if line.strip().startswith('|'): cur.append(line.strip())
        elif cur: out.append(cur); cur = []
    if cur: out.append(cur)
    res = []
    for t in out:
        rows = [[clean(c) for c in r.strip('|').split('|')] for r in t if not re.match(r'^\|[\s\-:|]+\|$', r)]
        if len(rows) > 1: res.append((rows[0], rows[1:]))
    return res
def clean(c):
    c = re.sub(r'</li>\s*<li>', '; ', c); c = re.sub(r'<[^>]+>', '', c); c = c.replace('**', '').replace('`', '')
    return html.unescape(c).strip()
