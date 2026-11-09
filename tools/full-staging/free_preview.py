#!/usr/bin/env python3
"""Generate a proposed /free menu from an existing file. Never edits input."""
from pathlib import Path
import argparse, re

# Proposed progression: (kit case, donate case, rilliks, kit). Requires in-game
# verification of dispatch, inventory overflow and persistence before deployment.
PLAN = {
  5:(1,2,300,None), 6:(1,2,350,'rabbit'), 7:(2,2,400,'rabbit'),
  8:(2,2,450,'hydra'), 9:(2,3,500,'hydra'), 10:(2,3,550,'cobra'),
  11:(3,3,600,'cobra'), 12:(3,3,650,'god'), 13:(3,4,700,'god'),
  14:(4,4,750,'angel'),
}

def rewrite(source):
    markers = list(re.finditer(r'(?m)^  free(\d+):\s*$', source))
    numbers=[int(m.group(1)) for m in markers]
    if numbers != list(range(1,15)):
        raise ValueError('expected exactly free1..free14 in order')
    chunks=[]
    for idx, m in enumerate(markers):
        end=markers[idx+1].start() if idx+1<len(markers) else len(source)
        s=source[m.start():end]; n=int(m.group(1))
        if n>=5:
            kits,donate,points,kit=PLAN[n]
            lore=["      - '&#F8BEFB&l┃ '","      - '&#F8BEFB&l┃ &fСодержимое:'"]
            if kit: lore.append("      - '&#F8BEFB&l┃  &7• &fНабор &#F8BEFB&l"+kit.upper()+"'")
            lore.extend([f"      - '&#F8BEFB&l┃  &7• &fКейс с наборами &7(x{kits})'",f"      - '&#F8BEFB&l┃  &7• &fКейс с донатом &7(x{donate})'",f"      - '&#F8BEFB&l┃  &7• &#F8BEFB{points} рилликов &fꐃ'", "      - '&#F8BEFB&l┃ '","      - '&#F8BEFB&l┃ &fТребуется: &#F8BEFB{need}'","      - '&#F8BEFB&l┃ '","      - '{status}'"])
            commands=[]
            if kit: commands.append(f"      - 'nkits:kit {kit} {{player}}'")
            commands.extend([f"      - 'bcases give {{player}} kits {kits}'",f"      - 'bcases give {{player}} donate {donate}'",f"      - 'p give {{player}} {points}'"])
            # Reject unknown layouts rather than deleting unrecognized fields.
            pattern=r'(?ms)^    lore:\n(?:      - .*\n)+    items: \[\]\n    commands:\n(?:      - .*\n)+'
            matches=list(re.finditer(pattern,s))
            if len(matches)!=1: raise ValueError(f'free{n} unsupported layout; no output written')
            replace='    lore:\n'+'\n'.join(lore)+'\n    items: []\n    commands:\n'+'\n'.join(commands)+'\n'
            q=matches[0]; s=s[:q.start()]+replace+s[q.end():]
        chunks.append(s)
    return source[:markers[0].start()]+''.join(chunks)

def main():
    p=argparse.ArgumentParser(); p.add_argument('input',type=Path); p.add_argument('output',type=Path); a=p.parse_args()
    if a.input.resolve()==a.output.resolve(): raise ValueError('output must be a distinct file')
    if a.output.exists(): raise ValueError('output already exists')
    result=rewrite(a.input.read_text(encoding='utf8'))
    with a.output.open('x',encoding='utf8') as f:f.write(result)
    print('Proposal only; not safe for production until command delivery is tested.')
if __name__=='__main__': main()
