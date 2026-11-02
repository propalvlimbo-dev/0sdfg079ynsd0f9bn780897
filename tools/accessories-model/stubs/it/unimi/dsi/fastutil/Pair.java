package it.unimi.dsi.fastutil;
/** Test-only stand-in for fastutil Pair: identical signatures, plain Java implementation. */
public interface Pair<L, R> {
    L left();
    R right();
    default L first() { return left(); }
    default R second() { return right(); }
    static <L, R> Pair<L, R> of(final L left, final R right) {
        return new Pair<L, R>() {
            public L left() { return left; }
            public R right() { return right; }
        };
    }
}
