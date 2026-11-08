package com.hokokrtet.hjobs.manager;

import com.hokokrtet.hjobs.HJobs;
import com.hokokrtet.hjobs.data.JobStat;
import java.io.File;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.bukkit.scheduler.BukkitRunnable;

public class DatabaseManager {

    private final HJobs plugin;
    private Connection connection;
    private final Object dbLock = new Object();
    private final Set<UUID> loadedPlayers = ConcurrentHashMap.newKeySet();

    public DatabaseManager(HJobs plugin) {
        this.plugin = plugin;
    }

    private Connection ensureConnectionLocked() throws SQLException {
        if (this.connection != null && !this.connection.isClosed()) {
            return this.connection;
        }
        File folder = this.plugin.getDataFolder();
        if (!folder.exists()) {
            folder.mkdirs();
        }
        String url = "jdbc:sqlite:" + new File(folder, "database.db").getAbsolutePath();
        try {
            Class.forName("org.sqlite.JDBC");
        } catch (ClassNotFoundException ignored) {
        }
        this.connection = DriverManager.getConnection(url);
        try (Statement pragma = this.connection.createStatement()) {
            pragma.execute("PRAGMA journal_mode=WAL");
            pragma.execute("PRAGMA synchronous=NORMAL");
            pragma.execute("PRAGMA busy_timeout=5000");
        } catch (SQLException ignored) {
        }
        return this.connection;
    }

    public void setupDatabase() {
        synchronized (this.dbLock) {
            try {
                Connection conn = ensureConnectionLocked();
                try (Statement st = conn.createStatement()) {
                    st.execute("CREATE TABLE IF NOT EXISTS boosters (id TEXT PRIMARY KEY, end_time LONG)");
                    st.execute("CREATE TABLE IF NOT EXISTS job_stats (uuid TEXT, job TEXT, sold_total INTEGER, daily_sold INTEGER, last_reset LONG, PRIMARY KEY(uuid, job))");
                }
            } catch (SQLException ex) {
                this.plugin.getLogger().severe("SQLite Error: " + ex.getMessage());
            }
        }
    }

    public void closeDatabase() {
        synchronized (this.dbLock) {
            try {
                if (this.connection != null && !this.connection.isClosed()) {
                    try (Statement st = this.connection.createStatement()) {
                        st.execute("PRAGMA wal_checkpoint(TRUNCATE)");
                    } catch (SQLException ignored) {
                    }
                    this.connection.close();
                }
            } catch (SQLException ex) {
                ex.printStackTrace();
            }
        }
    }

    public Map<String, JobStat> ensurePlayerStatsLoaded(UUID uuid) {
        if (uuid == null) {
            return new ConcurrentHashMap<>();
        }
        JobManager jm = this.plugin.getJobManager();
        if (this.loadedPlayers.contains(uuid)) {
            Map<String, JobStat> fast = jm.peekPlayerStats(uuid);
            if (fast != null) {
                return fast;
            }
        }

        synchronized (this.dbLock) {
            if (this.loadedPlayers.contains(uuid)) {
                Map<String, JobStat> existing = jm.peekPlayerStats(uuid);
                if (existing != null) {
                    return existing;
                }
            }

            ConcurrentHashMap<String, JobStat> merged = new ConcurrentHashMap<>();
            Map<String, JobStat> inMemory = jm.peekPlayerStats(uuid);
            if (inMemory != null) {
                merged.putAll(inMemory);
            }

            boolean querySucceeded = false;
            try {
                Connection conn = ensureConnectionLocked();
                try (PreparedStatement ps = conn.prepareStatement(
                        "SELECT job, sold_total, daily_sold, last_reset FROM job_stats WHERE uuid = ?")) {
                    ps.setString(1, uuid.toString());
                    try (ResultSet rs = ps.executeQuery()) {
                        while (rs.next()) {
                            String job = rs.getString("job");
                            int dbSoldTotal = rs.getInt("sold_total");
                            int dbDailySold = rs.getInt("daily_sold");
                            long dbLastReset = rs.getLong("last_reset");
                            if (job == null) {
                                continue;
                            }
                            JobStat mem = merged.get(job);
                            if (mem == null) {
                                merged.put(job, new JobStat(dbSoldTotal, dbDailySold, dbLastReset));
                            } else {
                                mem.soldItemsTotal = Math.max(mem.soldItemsTotal, dbSoldTotal);
                                if (dbLastReset > mem.lastReset) {
                                    mem.dailySold = dbDailySold;
                                    mem.lastReset = dbLastReset;
                                } else if (dbLastReset == mem.lastReset) {
                                    mem.dailySold = Math.max(mem.dailySold, dbDailySold);
                                }
                            }
                        }
                    }
                }
                querySucceeded = true;
            } catch (SQLException ex) {
                this.plugin.getLogger().warning("Error loading stats for " + uuid + ": " + ex.getMessage());
            }

            jm.setPlayerStats(uuid, merged);
            if (querySucceeded) {
                this.loadedPlayers.add(uuid);
            }
            return merged;
        }
    }

    public void loadPlayerStats(final UUID uuid) {
        if (uuid == null) {
            return;
        }
        if (this.plugin.isEnabled()) {
            new BukkitRunnable() {
                @Override
                public void run() {
                    ensurePlayerStatsLoaded(uuid);
                }
            }.runTaskAsynchronously(this.plugin);
        } else {
            ensurePlayerStatsLoaded(uuid);
        }
    }

    public void savePlayerStats(UUID uuid) {
        if (uuid == null || !this.loadedPlayers.contains(uuid)) {
            return;
        }
        Map<String, JobStat> stats = this.plugin.getJobManager().peekPlayerStats(uuid);
        if (stats == null || stats.isEmpty()) {
            return;
        }

        synchronized (this.dbLock) {
            Connection conn = null;
            try {
                conn = ensureConnectionLocked();
                conn.setAutoCommit(false);
                try (PreparedStatement ps = conn.prepareStatement(
                        "INSERT INTO job_stats (uuid, job, sold_total, daily_sold, last_reset) VALUES (?, ?, ?, ?, ?) "
                        + "ON CONFLICT(uuid, job) DO UPDATE SET "
                        + "sold_total = MAX(job_stats.sold_total, excluded.sold_total), "
                        + "daily_sold = excluded.daily_sold, "
                        + "last_reset = excluded.last_reset")) {
                    String uid = uuid.toString();
                    for (Map.Entry<String, JobStat> entry : stats.entrySet()) {
                        String job = entry.getKey();
                        JobStat stat = entry.getValue();
                        if (job == null || stat == null) {
                            continue;
                        }
                        ps.setString(1, uid);
                        ps.setString(2, job);
                        ps.setInt(3, stat.soldItemsTotal);
                        ps.setInt(4, stat.dailySold);
                        ps.setLong(5, stat.lastReset);
                        ps.addBatch();
                    }
                    ps.executeBatch();
                }
                conn.commit();
            } catch (SQLException ex) {
                if (conn != null) {
                    try {
                        conn.rollback();
                    } catch (SQLException ignored) {
                    }
                }
                this.plugin.getLogger().warning("Error saving stats for " + uuid + ": " + ex.getMessage());
            } finally {
                if (conn != null) {
                    try {
                        conn.setAutoCommit(true);
                    } catch (SQLException ignored) {
                    }
                }
            }
        }
    }

    public void savePlayerStatsAsync(final UUID uuid) {
        if (uuid == null) {
            return;
        }
        if (this.plugin.isEnabled()) {
            new BukkitRunnable() {
                @Override
                public void run() {
                    savePlayerStats(uuid);
                }
            }.runTaskAsynchronously(this.plugin);
        } else {
            savePlayerStats(uuid);
        }
    }

    public Map<String, Long> loadBoosters() {
        Map<String, Long> result = new ConcurrentHashMap<>();
        synchronized (this.dbLock) {
            try {
                Connection conn = ensureConnectionLocked();
                try (PreparedStatement ps = conn.prepareStatement(
                        "SELECT id, end_time FROM boosters WHERE end_time > ?")) {
                    ps.setLong(1, System.currentTimeMillis());
                    try (ResultSet rs = ps.executeQuery()) {
                        while (rs.next()) {
                            String id = rs.getString("id");
                            if (id != null) {
                                result.put(id, rs.getLong("end_time"));
                            }
                        }
                    }
                }
            } catch (SQLException ex) {
                this.plugin.getLogger().warning("Error loading boosters: " + ex.getMessage());
            }
        }
        return result;
    }

    public void saveBoosters(Map<String, Long> boosters) {
        if (boosters == null) {
            return;
        }
        synchronized (this.dbLock) {
            Connection conn = null;
            try {
                conn = ensureConnectionLocked();
                conn.setAutoCommit(false);
                try (PreparedStatement ps = conn.prepareStatement(
                        "REPLACE INTO boosters (id, end_time) VALUES (?, ?)")) {
                    for (Map.Entry<String, Long> entry : boosters.entrySet()) {
                        if (entry.getKey() != null && entry.getValue() != null) {
                            ps.setString(1, entry.getKey());
                            ps.setLong(2, entry.getValue());
                            ps.addBatch();
                        }
                    }
                    ps.executeBatch();
                }
                conn.commit();
                conn.setAutoCommit(true);
                try (PreparedStatement clean = conn.prepareStatement(
                        "DELETE FROM boosters WHERE end_time <= ?")) {
                    clean.setLong(1, System.currentTimeMillis());
                    clean.executeUpdate();
                }
            } catch (SQLException ex) {
                if (conn != null) {
                    try {
                        conn.rollback();
                    } catch (SQLException ignored) {
                    }
                }
                this.plugin.getLogger().warning("Error saving boosters: " + ex.getMessage());
            } finally {
                if (conn != null) {
                    try {
                        conn.setAutoCommit(true);
                    } catch (SQLException ignored) {
                    }
                }
            }
        }
    }

    public void startAutoSave() {
        new BukkitRunnable() {
            @Override
            public void run() {
                for (UUID uuid : plugin.getJobManager().getAllStatsKeys()) {
                    savePlayerStats(uuid);
                }
                saveBoosters(plugin.getJobManager().getBoosters());
            }
        }.runTaskTimerAsynchronously(this.plugin, 6000L, 6000L);
    }
}
