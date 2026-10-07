"""Summarize recorded raw model counts before user corrections; no fabricated results."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def summarize(rows):
    groups = defaultdict(list)
    allowed = {'sinandomeng', 'jasmine', 'buko_pandan'}
    for row in rows:
        if row.get('product') not in allowed:
            raise ValueError('Use one of the three rice product labels')
        if any(type(row.get(k)) is not int or row[k] < 0 for k in ('actual', 'predicted')):
            raise ValueError('Counts must be nonnegative whole visible sacks')
        if row.get('user_corrected') is not False:
            raise ValueError('Measurements must use original results before user correction')
        groups[(row['product'], row.get('condition', 'unspecified'))].append(row)
    out = []
    for (product, condition), items in sorted(groups.items()):
        out.append({'product': product, 'condition': condition, 'images': len(items),
                    'count_mae': sum(abs(r['predicted']-r['actual']) for r in items)/len(items),
                    'exact_count_rate': sum(r['predicted']==r['actual'] for r in items)/len(items)})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--records',required=True,help='JSON array of recorded uncorrected test counts')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    rows=json.loads(Path(a.records).read_text(encoding='utf-8'))
    if not isinstance(rows,list) or not rows:
        p.error('Provide measured test records; none are included with MOVIS')
    Path(a.output).write_text(json.dumps(summarize(rows),indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
