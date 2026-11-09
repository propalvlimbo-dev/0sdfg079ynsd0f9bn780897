#!/usr/bin/env python3
"""Cross-checks our compiled classes against the real ModelEngine jar.

Why this exists: v25 shipped a build where the compile-time stub of
`PivotOverrideRegistry` was an interface while the engine ships a class, so the
JVM threw `IncompatibleClassChangeError: Found class ..., but interface was
expected` the moment the mask was spawned. Nothing in the mock tests could see
that, because the mocks were built from the same wrong stub.

What is checked:

1. every stub of a `com/ticxo/...` type has the same kind (class / interface)
   as the real class in the engine jar;
2. every method declared by such a stub exists in the engine with the same
   descriptor, directly or inherited;
3. every method reference our own plugin classes make into `com/ticxo/...`
   resolves in the engine jar.

Usage: python3 verify_engine.py <classes-dir> <ModelEngine.jar>
Exit code 0 = clean, 1 = at least one mismatch (printed).
"""
import struct
import sys
import zipfile
from pathlib import Path

ENGINE_PREFIX = 'com/ticxo/'
# Our own test seam, not part of ModelEngine: the stub of ModelEngineAPI carries
# a Backend interface so the mock tests can swap the engine out.
OWN_STUBS = {'com/ticxo/modelengine/api/ModelEngineAPI$Backend'}
# methods every type inherits from Object; the compiler may reference them through
# an interface constant even when the declaring type is a class
OBJECT_METHODS = {'getClass', 'hashCode', 'equals', 'toString', 'notify', 'notifyAll', 'wait'}


# --------------------------------------------------------------------------- class file
def _parse(data):
    """Returns (access, this, super, interfaces, methods, pool)."""
    if data[:4] != b'\xca\xfe\xba\xbe':
        raise ValueError('not a class file')
    count = struct.unpack('>H', data[8:10])[0]
    pool = {}
    i, n = 10, 1
    while n < count:
        tag = data[i]
        i += 1
        if tag == 1:
            length = struct.unpack('>H', data[i:i + 2])[0]
            i += 2
            pool[n] = data[i:i + length].decode('utf-8', 'replace')
            i += length
        elif tag == 7:                       # Class -> name index
            pool[n] = ('class', struct.unpack('>H', data[i:i + 2])[0])
            i += 2
        elif tag in (8, 16, 19, 20):         # String, MethodType, Module, Package
            i += 2
        elif tag == 15:                      # MethodHandle
            i += 3
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            i += 4
        elif tag in (5, 6):                  # long / double take two slots
            i += 8
            n += 1
        else:
            raise ValueError('constant pool tag ' + str(tag))
        n += 1

    def cls(index):
        entry = pool.get(struct.unpack('>H', data[index:index + 2])[0])
        return pool.get(entry[1]) if isinstance(entry, tuple) else None

    access = struct.unpack('>H', data[i:i + 2])[0]
    this = cls(i + 2)
    super_name = cls(i + 4)
    i += 6
    iface_count = struct.unpack('>H', data[i:i + 2])[0]
    i += 2
    interfaces = [cls(j) for j in range(i, i + 2 * iface_count, 2)]
    i += 2 * iface_count

    def skip_members(index):
        total = struct.unpack('>H', data[index:index + 2])[0]
        index += 2
        out = []
        for _ in range(total):
            m_access, m_name, m_desc = struct.unpack('>HHH', data[index:index + 6])
            index += 6
            attrs = struct.unpack('>H', data[index:index + 2])[0]
            index += 2
            for _ in range(attrs):
                _name, size = struct.unpack('>HI', data[index:index + 6])
                index += 6 + size
            out.append((pool.get(m_name), pool.get(m_desc)))
        return out, index

    _, i = skip_members(i)                   # fields
    methods, _ = skip_members(i)
    return access, this, super_name, interfaces, methods, pool


class Engine:
    """Method index of a ModelEngine jar, lazy and cached."""

    def __init__(self, jar):
        self.zip = zipfile.ZipFile(jar)
        self.names = set(self.zip.namelist())
        self.cache = {}

    def info(self, name):
        key = name + '.class'
        if key not in self.cache:
            if key not in self.names:
                self.cache[key] = None
            else:
                self.cache[key] = _parse(self.zip.read(key))
        return self.cache[key]

    def has_method(self, owner, name, descriptor, seen=None):
        seen = seen or set()
        if owner in seen:
            return False
        seen.add(owner)
        info = self.info(owner)
        if info is None:
            return False
        _, this, super_name, interfaces, methods, _ = info
        for m_name, m_desc in methods:
            if m_name == name and m_desc == descriptor:
                return True
        if super_name and self.has_method(super_name, name, descriptor, seen):
            return True
        return any(self.has_method(i, name, descriptor, seen) for i in interfaces if i)


def scan_classes(root):
    for path in sorted(Path(root).rglob('*.class')):
        yield path.relative_to(root).as_posix()[:-len('.class')], path.read_bytes()


def main():
    classes_dir = Path(sys.argv[1])
    engine = Engine(sys.argv[2])
    problems = []

    for name, data in scan_classes(classes_dir):
        if not name.startswith(ENGINE_PREFIX) or name in OWN_STUBS:
            continue
        access, this, super_name, interfaces, methods, _ = _parse(data)
        real = engine.info(name)
        if real is None:
            problems.append(f'{name}: stub has no counterpart in the engine jar')
            continue
        real_access, _, real_super, real_interfaces, real_methods, _ = real
        if bool(access & 0x0200) != bool(real_access & 0x0200):
            kind = 'interface' if access & 0x0200 else 'class'
            real_kind = 'interface' if real_access & 0x0200 else 'class'
            problems.append(f'{name}: stub is a {kind}, the engine ships a {real_kind}')
        for m_name, m_desc in methods:
            if m_name is None:
                continue
            if (m_name, m_desc) in real_methods:
                continue
            if engine.has_method(name, m_name, m_desc):
                continue
            problems.append(f'{name}: method {m_name}{m_desc} does not exist in the engine')

    # every call our own classes make into the engine has to resolve, and the
    # constant-pool tag has to match the target: InterfaceMethodref (tag 11) on a
    # class compiles to invokeinterface and dies with IncompatibleClassChangeError
    for name, data in scan_classes(classes_dir):
        for owner, m_name, m_desc, tag in method_refs(data):
            if not owner.startswith(ENGINE_PREFIX) or owner in OWN_STUBS:
                continue
            real = engine.info(owner)
            if real is None:
                problems.append(f'{name}: call to {owner} — no such class in the engine')
                continue
            if not engine.has_method(owner, m_name, m_desc):
                problems.append(f'{name}: call to {owner}.{m_name}{m_desc} does not resolve')
                continue
            is_interface = bool(real[0] & 0x0200)
            object_method = m_name in OBJECT_METHODS
            if tag == 11 and not is_interface and not object_method:
                problems.append(f'{name}: invokeinterface on {owner} which is a class '
                                f'({m_name}{m_desc}) — would throw IncompatibleClassChangeError')
            elif tag == 10 and is_interface and not object_method:
                problems.append(f'{name}: invokevirtual on {owner} which is an interface '
                                f'({m_name}{m_desc})')

    if problems:
        print('engine cross-check FAILED')
        for line in problems:
            print('  -', line)
        return 1
    print('engine cross-check ok')
    return 0


def method_refs(data):
    """Yields (owner, name, descriptor) for every Methodref / InterfaceMethodref."""
    count = struct.unpack('>H', data[8:10])[0]
    pool = {}
    i, n = 10, 1
    while n < count:
        tag = data[i]
        i += 1
        if tag == 1:
            length = struct.unpack('>H', data[i:i + 2])[0]
            i += 2
            pool[n] = ('utf8', data[i:i + length].decode('utf-8', 'replace'))
            i += length
        elif tag == 7:
            pool[n] = ('class', struct.unpack('>H', data[i:i + 2])[0])
            i += 2
        elif tag in (8, 16, 19, 20):
            i += 2
        elif tag == 15:
            i += 3
        elif tag in (9, 10, 11):             # Fieldref / Methodref / InterfaceMethodref
            pool[n] = ('ref',) + struct.unpack('>HH', data[i:i + 4]) + (tag,)
            i += 4
        elif tag == 12:                      # NameAndType -> (name, descriptor)
            pool[n] = ('nat',) + struct.unpack('>HH', data[i:i + 4])
            i += 4
        elif tag in (3, 4, 17, 18):
            i += 4
        elif tag in (5, 6):
            i += 8
            n += 1
        else:
            raise ValueError('constant pool tag ' + str(tag))
        n += 1
    for entry in pool.values():
        if not isinstance(entry, tuple) or entry[0] != 'ref':
            continue
        _, class_index, nat_index, entry_tag = entry
        if entry_tag == 9:                  # Fieldref: not a method call
            continue
        cls = pool.get(class_index)
        nat = pool.get(nat_index)
        if not cls or not nat:
            continue
        owner = pool.get(cls[1])
        nat_name = pool.get(nat[1])
        nat_desc = pool.get(nat[2])
        if not owner or not nat_name or not nat_desc:
            continue
        yield owner[1], nat_name[1], nat_desc[1], entry_tag


if __name__ == '__main__':
    sys.exit(main())
