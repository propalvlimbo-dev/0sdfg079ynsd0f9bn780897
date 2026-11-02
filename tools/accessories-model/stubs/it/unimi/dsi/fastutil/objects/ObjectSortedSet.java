package it.unimi.dsi.fastutil.objects;
public interface ObjectSortedSet<K> extends ObjectSet<K>, java.util.SortedSet<K> {
    ObjectBidirectionalIterator<K> iterator();
}
