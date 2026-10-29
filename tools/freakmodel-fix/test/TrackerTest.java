import org.bukkit.*; import org.bukkit.entity.Player; import org.bukkit.util.Vector;
import pw.elytrix.freakmodel.PlayerBodyTracker;

public class TrackerTest {
    static final World A = () -> "world", B = () -> "nether";
    static class FakePlayer implements Player {
        World world=A; double x, z, vertical; float head, body; boolean forward, flying, ground=true, vehicle;
        public Location getLocation(Location l) { l.set(world,x,0,z,head); return l; }
        public float getBodyYaw(){return body;}
        public Input getCurrentInput(){return new Input(){ public boolean isForward(){return forward;} public boolean isBackward(){return false;} public boolean isLeft(){return false;} public boolean isRight(){return false;} };}
        public boolean isFlying(){return flying;} public boolean isGliding(){return false;} public boolean isOnGround(){return ground;} public boolean isInsideVehicle(){return vehicle;} public boolean isSwimming(){return false;} public boolean isSprinting(){return false;} public Vector getVelocity(){return new Vector(vertical);}
    }
    static void check(boolean b, String message){if(!b)throw new AssertionError(message);}
    public static void main(String[] args) {
        FakePlayer p=new FakePlayer(); p.head=20; p.body=10;
        PlayerBodyTracker t=new PlayerBodyTracker(); t.resetToPlayer(p);
        check(t.getBodyYaw()==10, "reset samples body, not head");
        Location event=new Location(A,0,0,0); event.set(A, 1, 0, 0, 170);
        t.stepFromPacket(p,event); t.stepFromPacket(p,event);
        check(t.getBodyYaw()==10, "packet count must not simulate body turn");
        p.body=179; p.head=170; t.stepServerTick(p); check(t.getBodyYaw()==179, "server body");
        p.body=-179; t.stepServerTick(p); check(t.getLastTickTurnSpeed()==2, "angle wrap");
        p.forward=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.WALK,"walk");
        p.flying=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.FLY,"flight");
        t.resetToYaw(60); event.set(B,1000,0,1000,60); p.world=B; p.body=40; p.flying=false;
        t.stepFromPacket(p,event); check(t.getHorizSpeedBlocksPerTick()==0 && t.getBodyYaw()==40,"teleport baseline");
        p.body=Float.NaN; p.head=90; t.stepServerTick(p); check(t.getBodyYaw()==90,"non-finite fallback");
        check(PlayerBodyTracker.wrapDegrees(181)==-179,"wrap");
        System.out.println("Tracker tests passed");
    }
}
