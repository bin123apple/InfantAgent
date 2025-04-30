import json
import re

input_path = 'predictions/predictions.jsonl'
output_path = 'submission.jsonl'

final_pat = re.compile(r"FINAL ANSWER:\s*(.*)", re.IGNORECASE)

with open(input_path, 'r', encoding='utf-8') as infile, \
     open(output_path, 'w', encoding='utf-8') as outfile:
    for line in infile:
        data = json.loads(line)
        raw = data.get('model_answer', '')
        m = final_pat.search(raw)
        final = m.group(1).strip() if m else raw.strip()

        output = {
            'task_id': data.get('task_id'),
            'model_answer': final,
            'reasoning_trace': data.get('reasoning_trace', ''),
        }
        json.dump(output, outfile, ensure_ascii=False)
        outfile.write('\n')

