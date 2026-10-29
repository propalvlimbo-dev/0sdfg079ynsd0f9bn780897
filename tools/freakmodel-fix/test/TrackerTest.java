import org.bukkit.*; import org.bukkit.entity.Entity; import org.bukkit.entity.Player; import org.bukkit.util.Vector;
import pw.elytrix.freakmodel.PlayerBodyTracker;

public class TrackerTest {
    static final World A = () -> "world", B = () -> "nether";
    static class FakePlayer implements Player {
        World world=A; double x, z, vertical; float head, staleBody; boolean forward, backward, left, right, flying, ground=true, vehicle; float vehicleYaw;
        public Location getLocation(Location l) { l.set(world,x,0,z,head); return l; }
        public float getBodyYaw(){return staleBody;}
        public Input getCurrentInput(){return new Input(){ public boolean isForward(){return forward;} public boolean isBackward(){return backward;} public boolean isLeft(){return left;} public boolean isRight(){return right;} };}
        public boolean isFlying(){return flying;} public boolean isGliding(){return false;} public boolean isOnGround(){return ground;} public boolean isInsideVehicle(){return vehicle;}
        public Entity getVehicle() { return vehicle ? l -> {l.set(world,x,0,z,vehicleYaw); return l;} : null; }
        public boolean isSwimming(){return false;} public boolean isSprinting(){return false;} public Vector getVelocity(){return new Vector(vertical);}
    }
    static void check(boolean b, String message){if(!b)throw new AssertionError(message);}
    static void near(float actual, float expected, String message) {check(Math.abs(PlayerBodyTracker.wrapDegrees(actual-expected)) < 0.001, message+": got "+actual+", expected "+expected);}
    public static void main(String[] args) {
        for (float facing : new float[]{0, 90, 180, -90}) {
            FakePlayer cardinal = new FakePlayer(); cardinal.head=facing; cardinal.staleBody=0;
            PlayerBodyTracker c = new PlayerBodyTracker(); c.resetToPlayer(cardinal);
            near(c.getBodyYaw(), facing, "spawn facing " + facing);
            double angle = Math.toRadians(facing);
            cardinal.x = Math.sin(angle) * 0.2; cardinal.z = -Math.cos(angle) * 0.2;
            c.stepServerTick(cardinal); near(c.getBodyYaw(), facing, "backward at " + facing);
        }
        FakePlayer p=new FakePlayer(); p.head=90; p.staleBody=0;
        PlayerBodyTracker t=new PlayerBodyTracker(); t.resetToPlayer(p);
        near(t.getBodyYaw(),90,"reset uses facing, not stale server body");
        p.head=120; t.stepServerTick(p); near(t.getBodyYaw(),90,"small head-only turn");
        p.head=180; t.stepServerTick(p); near(t.getBodyYaw(),130,"large stationary turn follows without stale server body");
        Location event=new Location(A,0,0,0); event.set(A,1,0,0,180);
        for(int i=0;i<25;i++) t.stepFromPacket(p,event);
        near(t.getBodyYaw(),130,"duplicate packets do not advance body");
        event.set(A,1,0,0,-60); t.stepFromPacket(p,event);
        near(t.getBodyYaw(),-110,"sharp turn responds before server tick");
        for(int i=0;i<25;i++) t.stepFromPacket(p,event);
        near(t.getBodyYaw(),-110,"duplicate sharp-turn packets remain stable");
        p.head=0; p.x=0; p.z=0; t.resetToPlayer(p);
        p.z=-0.2; t.stepServerTick(p); near(t.getBodyYaw(),0,"walking backwards faces forward");
        p.x=0.2; t.stepServerTick(p); check(Math.abs(t.getBodyYaw())>1,"strafing turns body");
        check(Math.abs(PlayerBodyTracker.wrapDegrees(p.head-t.getBodyYaw()))<=50,"head/body bound");
        p.forward=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.WALK,"walk mode");
        p.flying=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.FLY,"flight mode");
        p.flying=false; p.head=179; t.resetToPlayer(p); p.head=-179; t.stepServerTick(p); near(t.getBodyYaw(),179,"wrap through 180");
        check(t.getLastTickTurnSpeed()<1,"no full-turn wrap jump");
        p.world=B; p.x=1000; p.z=1000; p.head=60; t.stepServerTick(p);
        near(t.getBodyYaw(),60,"world change reset"); check(t.getHorizSpeedBlocksPerTick()==0,"world change speed reset");
        p.x+=100; p.head=-100; t.stepServerTick(p); near(t.getBodyYaw(),-100,"teleport reset");
        p.head=30; t.resetToPlayer(p); p.head=80; t.notifyArmSwing(); t.stepServerTick(p); near(t.getBodyYaw(),45,"arm swing turns body");
        p.vehicle=true; p.vehicleYaw=120; p.head=120; t.stepServerTick(p); near(t.getBodyYaw(),120,"vehicle facing");
        p.vehicle=false; p.head=Float.NaN; t.stepServerTick(p); check(Float.isFinite(t.getBodyYaw()),"non-finite yaw");

        // Packet previews are visible immediately but must not change the once-
        // per-tick simulation, even when there are many packets in one tick.
        FakePlayer move = new FakePlayer(); move.forward=true; move.left=true; move.right=true;
        PlayerBodyTracker withPackets=new PlayerBodyTracker(), tickOnly=new PlayerBodyTracker();
        withPackets.resetToPlayer(move); tickOnly.resetToPlayer(move);
        move.head=90; move.x=-0.2;
        Location sharp=new Location(A,0,0,0); sharp.set(A,move.x,0,move.z,move.head);
        for(int i=0;i<25;i++) withPackets.stepFromPacket(move,sharp);
        near(withPackets.getBodyYaw(),40,"sharp turn preview");
        withPackets.stepServerTick(move); tickOnly.stepServerTick(move);
        near(withPackets.getBodyYaw(),40,"sharp walking turn must not be double-counted");
        near(withPackets.getBodyYaw(),tickOnly.getBodyYaw(),"packet preview vs tick-only turn");
        check(withPackets.getMode()==PlayerBodyTracker.MovementMode.WALK,"W+A+D remains forward walking");
        for (int i=0;i<80;i++) {
            move.head=(i%4==0 ? 179 : i%4==1 ? -179 : i%4==2 ? 35 : -85);
            move.x += i%3==0 ? 0.11 : -0.08;
            move.z += i%2==0 ? 0.12 : -0.07;
            sharp.set(A,move.x,0,move.z,move.head);
            for (int j=0;j<5;j++) withPackets.stepFromPacket(move,sharp);
            withPackets.stepServerTick(move); tickOnly.stepServerTick(move);
            near(withPackets.getBodyYaw(),tickOnly.getBodyYaw(),"packet independent tick " + i);
        }
        FakePlayer keys=new FakePlayer(); keys.left=true; keys.right=true;
        PlayerBodyTracker cancelled=new PlayerBodyTracker(); cancelled.resetToPlayer(keys);
        for(int i=0;i<10;i++) cancelled.stepServerTick(keys);
        check(cancelled.getMode()==PlayerBodyTracker.MovementMode.IDLE,"A+D alone cancel");
        keys.left=false; keys.right=false; keys.forward=true; keys.backward=true;
        for(int i=0;i<10;i++) cancelled.stepServerTick(keys);
        check(cancelled.getMode()==PlayerBodyTracker.MovementMode.IDLE,"W+S alone cancel");
        keys.backward=false; keys.left=true; keys.right=true;
        cancelled.stepServerTick(keys);
        check(cancelled.getMode()==PlayerBodyTracker.MovementMode.WALK,"W+A+D is forward");
        System.out.println("Tracker tests passed");
    }
}
