package com.ticxo.modelengine.api.entity;
import com.ticxo.modelengine.api.entity.data.IEntityData;
import com.ticxo.modelengine.api.nms.entity.wrapper.BodyRotationController;
import com.ticxo.modelengine.api.nms.impl.DefaultBodyRotationController;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import java.util.UUID;

public class Dummy<T> implements BaseEntity {
    private final UUID uuid = UUID.randomUUID();
    private final T original;
    private boolean removed;
    private float yBodyRot;
    private float yHeadRot;
    private float xHeadRot;
    private int renderRadius = 32;
    public IEntityData mockData;
    private final DefaultBodyRotationController rot = new DefaultBodyRotationController(this);

    public Dummy(T original) {
        this.original = original;
    }

    public T getOriginal() { return original; }
    @Override public int getEntityId() { return 9001; }
    @Override public UUID getUUID() { return uuid; }
    @Override public IEntityData getData() { return mockData; }
    public BodyRotationController getBodyRotationController() { return rot; }
    public void setRenderRadius(int radius) { this.renderRadius = radius; }
    public int getRenderRadius() { return renderRadius; }
    public void syncLocation(Location location) {}
    public void setForceViewing(Player player, boolean flag) {}
    public void setDetectingPlayers(boolean flag) {}
    public void setRemoved(boolean flag) { this.removed = flag; }
    public boolean isRemoved() { return removed; }
    public void setYBodyRot(float v) { this.yBodyRot = v; }
    public void setYHeadRot(float v) { this.yHeadRot = v; }
    public void setXHeadRot(float v) { this.xHeadRot = v; }
}
