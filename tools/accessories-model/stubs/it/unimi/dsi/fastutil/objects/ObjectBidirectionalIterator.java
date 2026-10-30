package it.unimi.dsi.fastutil.objects;
public interface ObjectBidirectionalIterator<K> extends ObjectIterator<K> {
    boolean hasPrevious();
    K previous();
}
