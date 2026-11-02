package it.unimi.dsi.fastutil.ints;
import java.util.Set;
/** Helper building the int set views used by the stand-ins. */
public final class IntSets {
    private IntSets() {}
    public static IntSet wrap(final Set<Integer> backing) {
        return new IntSet() {
            public int size() { return backing.size(); }
            public boolean isEmpty() { return backing.isEmpty(); }
            public boolean contains(Object o) { return backing.contains(o); }
            public boolean contains(int k) { return backing.contains(Integer.valueOf(k)); }
            public boolean add(Integer k) { return backing.add(k); }
            public boolean add(int k) { return backing.add(Integer.valueOf(k)); }
            public boolean remove(Object o) { return backing.remove(o); }
            public void clear() { backing.clear(); }
            public IntIterator iterator() { return IntIterators.wrap(backing.iterator()); }
            public boolean containsAll(java.util.Collection<?> c) { return backing.containsAll(c); }
            public boolean addAll(java.util.Collection<? extends Integer> c) { return backing.addAll(c); }
            public boolean retainAll(java.util.Collection<?> c) { return backing.retainAll(c); }
            public boolean removeAll(java.util.Collection<?> c) { return backing.removeAll(c); }
            public Object[] toArray() { return backing.toArray(); }
            public <T> T[] toArray(T[] a) { return backing.toArray(a); }
        };
    }
}
