package pw.elytrix.freakmodel;
import com.ticxo.modelengine.api.model.ModeledEntity;

/** Compile-time stand-in for PlayerAuraAttachment already shipped in ElytrixFreakModel.jar. */
public final class PlayerAuraAttachment {
    public static void syncModeledEntityImmediately(ModeledEntity entity, float bodyYaw) {
        if (entity == null || !Float.isFinite(bodyYaw)) return;
        entity.setYBodyRotImmediately(bodyYaw);
        entity.setYHeadRotImmediately(bodyYaw);
        entity.setXHeadRotImmediately(0.0F);
        entity.setRotationTick(-1);
    }
}
