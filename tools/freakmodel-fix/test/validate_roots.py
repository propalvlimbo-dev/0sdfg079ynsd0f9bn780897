#!/usr/bin/env python3
"""Geometric checks for the shoulder roots; not an in-game rendering test."""
import itertools, json, math
from pathlib import Path

root = Path(__file__).resolve().parents[3]
model = json.loads((root / 'plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel').read_text())
elements = {e['name']: e for e in model['elements']}
wing_root = next(x for x in model['outliner'] if isinstance(x, dict) and x.get('name') == 'wings_root')
assert wing_root['origin'] == [0.0, 20.4, 0.0]

# The left side must be an exact mirror of the right.
for label in ('joint', 'upper', 'lower'):
    a = elements['shoulder_root_right_' + label]
    b = elements['shoulder_root_left_' + label]
    assert a['from'][0] == -b['to'][0] and a['to'][0] == -b['from'][0]
    assert a['from'][1:] == b['from'][1:] and a['to'][1:] == b['to'][1:]
    assert a['rotation'][2] == -b['rotation'][2]

def rotate_z(x, y, angle, origin):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    dx, dy = x-origin[0], y-origin[1]
    return origin[0]+dx*c-dy*s, origin[1]+dx*s+dy*c

def corners2d(e):
    x1,y1=e['from'][:2]; x2,y2=e['to'][:2]
    return [rotate_z(x,y,e['rotation'][2],e['origin']) for x,y in
            ((x1,y1),(x2,y1),(x2,y2),(x1,y2))]

def intersects(a,b):
    for polygon in (a,b):
        for i,p in enumerate(polygon):
            q=polygon[(i+1)%len(polygon)]; axis=(q[1]-p[1],p[0]-q[0])
            va=[x*axis[0]+y*axis[1] for x,y in a]
            vb=[x*axis[0]+y*axis[1] for x,y in b]
            if max(va)<min(vb) or max(vb)<min(va): return False
    return True

for side, wing_index in [('right',0),('left',6)]:
    joint=elements[f'shoulder_root_{side}_joint']
    wing=elements[f'wing_{wing_index}']
    assert intersects(corners2d(joint),corners2d(wing)), (side,'root does not touch wing')
    assert max(joint['from'][2],wing['from'][2]) <= min(joint['to'][2],wing['to'][2])

    bone = next(x for x in wing_root['children'] if x['name']==f'{side}_wing_inner')
    assert bone['origin']==[0.0,20.4,0.0]
    rotations=[]
    for anim in model['animations']:
        for animator in anim['animators'].values():
            if animator.get('name') == bone['name']:
                for key in animator['keyframes']:
                    if key['channel']=='rotation':
                        values=key['data_points'][0]
                        angles=tuple(float(values[a]) for a in ('x','y','z'))
                        assert angles[0]==0
                        rotations.append(angles)
    assert rotations
    ymin=math.floor(min(v[1] for v in rotations)); ymax=math.ceil(max(v[1] for v in rotations))
    zmin=math.floor(min(v[2] for v in rotations)); zmax=math.ceil(max(v[2] for v in rotations))
    for label in ('joint','upper','lower'):
        e=elements[f'shoulder_root_{side}_{label}']
        min_depth=float('inf')
        for x,y,z in itertools.product(*zip(e['from'],e['to'])):
            x,y=rotate_z(x,y,e['rotation'][2],e['origin'])
            # Check both possible Y/Z transform orders over the animation's
            # integer-degree envelope, a conservative approximation.
            for ay in range(ymin,ymax+1):
                cy,sy=math.cos(math.radians(ay)),math.sin(math.radians(ay))
                depth_y_first=-x*sy+z*cy
                for az in range(zmin,zmax+1):
                    x_after_z,_=rotate_z(x,y,az,bone['origin'])
                    depth_z_first=-x_after_z*sy+z*cy
                    min_depth=min(min_depth,depth_y_first,depth_z_first)
        assert min_depth >= 3.9, (side,label,min_depth)
        print(side, label, 'minimum sampled back depth:', round(min_depth,3))
print('Root geometry checks passed; actual client rendering is not verified.')
