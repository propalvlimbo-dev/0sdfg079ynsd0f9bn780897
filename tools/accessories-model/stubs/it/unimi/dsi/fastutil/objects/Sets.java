package it.unimi.dsi.fastutil.objects;
import java.util.LinkedHashSet;
import java.util.Set;
/** Small helper building the set views used by the stand-ins. */
public final class Sets {
    private Sets() {}
    public static <K> ObjectSet<K> objectSet(final Set<K> backing) {
        return new ObjectSet<K>() {
            public int size() { return backing.size(); }
            public boolean isEmpty() { return backing.isEmpty(); }
            public boolean contains(Object o) { return backing.contains(o); }
            public boolean add(K k) { return backing.add(k); }
            public boolean remove(Object o) { return backing.remove(o); }
            public void clear() { backing.clear(); }
            public ObjectIterator<K> iterator() {
                final java.util.Iterator<K> it = backing.iterator();
                return new ObjectIterator<K>() {
                    public boolean hasNext() { return it.hasNext(); }
                    public K next() { return it.next(); }
                    public void remove() { it.remove(); }
                };
            }
            public boolean containsAll(java.util.Collection<?> c) { return backing.containsAll(c); }
            public boolean addAll(java.util.Collection<? extends K> c) { return backing.addAll(c); }
            public boolean retainAll(java.util.Collection<?> c) { return backing.retainAll(c); }
            public boolean removeAll(java.util.Collection<?> c) { return backing.removeAll(c); }
            public Object[] toArray() { return backing.toArray(); }
            public <T> T[] toArray(T[] a) { return backing.toArray(a); }
        };
    }
    public static <K> ObjectSortedSet<K> objectSortedSet(final java.util.List<K> order) {
        final LinkedHashSet<K> set = new LinkedHashSet<K>(order);
        return new ObjectSortedSet<K>() {
            public int size() { return set.size(); }
            public boolean isEmpty() { return set.isEmpty(); }
            public boolean contains(Object o) { return set.contains(o); }
            public boolean add(K k) { return set.add(k); }
            public boolean remove(Object o) { return set.remove(o); }
            public void clear() { set.clear(); }
            public ObjectBidirectionalIterator<K> iterator() {
                final java.util.List<K> list = new java.util.ArrayList<K>(set);
                return new ObjectBidirectionalIterator<K>() {
                    private int i = 0;
                    public boolean hasNext() { return i < list.size(); }
                    public K next() { return list.get(i++); }
                    public boolean hasPrevious() { return i > 0; }
                    public K previous() { return list.get(--i); }
                };
            }
            public boolean containsAll(java.util.Collection<?> c) { return set.containsAll(c); }
            public boolean addAll(java.util.Collection<? extends K> c) { return set.addAll(c); }
            public boolean retainAll(java.util.Collection<?> c) { return set.retainAll(c); }
            public boolean removeAll(java.util.Collection<?> c) { return set.removeAll(c); }
            public Object[] toArray() { return set.toArray(); }
            public <T> T[] toArray(T[] a) { return set.toArray(a); }
            public java.util.Comparator<? super K> comparator() { return null; }
            public K first() { return set.iterator().next(); }
            public K last() { K last = null; for (K k : set) last = k; return last; }
            public ObjectSortedSet<K> subSet(K a, K b) { throw new UnsupportedOperationException(); }
            public ObjectSortedSet<K> headSet(K a) { throw new UnsupportedOperationException(); }
            public ObjectSortedSet<K> tailSet(K a) { throw new UnsupportedOperationException(); }
        };
    }
}
