"""Build the daily review JSON file by stripping newlines from raw_output."""
import json
import re

path = '/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-07-01_20260701_213006.json'

with open(path, 'r', encoding='utf-8') as f:
    raw = f.read()

# Find raw_output: it has HTML with literal newlines and tabs that need to become \\n and \\t in JSON
# Strategy: parse line by line. The file has structure where raw_output starts at a specific line.
lines = raw.split('\n')
out_lines = []
in_raw = False
buf = []
for i, line in enumerate(lines):
    if '"raw_output":' in line:
        # Start of raw_output value
        # Split at "raw_output": to find the value start
        idx = line.index('"raw_output":')
        prefix = line[:idx + len('"raw_output":')]
        out_lines.append(prefix)
        rest = line[idx + len('"raw_output":'):]
        # The rest starts with a space then a quote then content then quote-comma
        # But the value may have a literal newline after the opening quote
        # Capture everything from first quote
        # Look for the first " in rest
        m = re.match(r'^(\s*")(.*?)("?,?\s*)$', rest, re.DOTALL)
        if m:
            opening = m.group(1)  # includes the opening quote and leading whitespace
            content = m.group(2)
            trailing = m.group(3)  # closing quote and trailing comma
            # content has actual newlines/tabs as control chars - we need to escape them
            # But we don't want to escape HTML tag chars
            # JSON only requires escaping: ", \, control chars (< 0x20)
            escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            # Now combine: opening quote, escaped content, trailing
            out_lines.append(opening + escaped + trailing)
        else:
            out_lines.append(line)
        in_raw = False
    else:
        out_lines.append(line)

new_text = '\n'.join(out_lines)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)

# Now try to parse it
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print('SUCCESS: valid JSON')
    print('Keys:', list(data.keys()))
    print('Position reviews:', len(data['result_payload']['position_review']))
    print('Lesson items:', len(data['result_payload']['lesson_items']))
    print('Raw output chars:', len(data['raw_output']))
    print('Market phase:', data['summary']['market_phase'])
except json.JSONDecodeError as e:
    print('FAILED:', e)
    # Show area around error
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    print('Context at', e.pos, ':')
    print(repr(content[max(0, e.pos-100):e.pos+100]))
