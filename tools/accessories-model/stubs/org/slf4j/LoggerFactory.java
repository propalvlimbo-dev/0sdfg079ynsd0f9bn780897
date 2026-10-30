package org.slf4j;
/** Test-only silent logger factory stand-in. */
public final class LoggerFactory {
    private LoggerFactory() {}
    public static Logger getLogger(String name) { return new Silent(name); }
    public static Logger getLogger(Class<?> type) { return new Silent(type.getName()); }
    private static final class Silent implements Logger {
        private final String name;
        Silent(String name) { this.name = name; }
        public String getName() { return name; }
        public boolean isTraceEnabled() { return false; }
        public void trace(String m) { }
        public void trace(String f, Object a) { }
        public void trace(String f, Object a, Object b) { }
        public void trace(String f, Object... a) { }
        public void trace(String m, Throwable t) { }
        public boolean isDebugEnabled() { return false; }
        public void debug(String m) { }
        public void debug(String f, Object a) { }
        public void debug(String f, Object a, Object b) { }
        public void debug(String f, Object... a) { }
        public void debug(String m, Throwable t) { }
        public boolean isInfoEnabled() { return false; }
        public void info(String m) { }
        public void info(String f, Object a) { }
        public void info(String f, Object a, Object b) { }
        public void info(String f, Object... a) { }
        public void info(String m, Throwable t) { }
        public boolean isWarnEnabled() { return false; }
        public void warn(String m) { }
        public void warn(String f, Object a) { }
        public void warn(String f, Object a, Object b) { }
        public void warn(String f, Object... a) { }
        public void warn(String m, Throwable t) { }
        public boolean isErrorEnabled() { return false; }
        public void error(String m) { }
        public void error(String f, Object a) { }
        public void error(String f, Object a, Object b) { }
        public void error(String f, Object... a) { }
        public void error(String m, Throwable t) { }
    }
}
