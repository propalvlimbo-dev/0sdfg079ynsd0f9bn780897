import org.bukkit.*; import org.bukkit.entity.Entity; import org.bukkit.entity.Player; import org.bukkit.util.Vector;
import pw.elytrix.freakmodel.PlayerBodyTracker;

public class TrackerTest {
    static final World A = () -> "world", B = () -> "nether";
    static class FakePlayer implements Player {
        World world=A; double x, z, vertical; float head, staleBody; boolean forward, backward, left, right, flying, gliding, swimming, ground=true, vehicle; float vehicleYaw;
        public Location getLocation(Location l) { l.set(world,x,0,z,head); return l; }
        public float getBodyYaw(){return staleBody;}
        public Input getCurrentInput(){return new Input(){ public boolean isForward(){return forward;} public boolean isBackward(){return backward;} public boolean isLeft(){return left;} public boolean isRight(){return right;} };}
        public boolean isFlying(){return flying;} public boolean isGliding(){return gliding;} public boolean isOnGround(){return ground;} public boolean isInsideVehicle(){return vehicle;}
        public Entity getVehicle() { return vehicle ? l -> {l.set(world,x,0,z,vehicleYaw); return l;} : null; }
        public boolean isSwimming(){return swimming;} public boolean isSprinting(){return false;} public Vector getVelocity(){return new Vector(vertical);}
    }
    static void check(boolean b, String message){if(!b)throw new AssertionError(message);}
    static void near(float actual, float expected, String message) {check(Math.abs(PlayerBodyTracker.wrapDegrees(actual-expected)) < 0.001, message+": got "+actual+", expected "+expected);}
    public static void main(String[] args) {
        for (float facing : new float[]{0, 90, 180, -90}) {
            FakePlayer cardinal = new FakePlayer(); cardinal.head=facing; cardinal.staleBody=0;
            PlayerBodyTracker c = new PlayerBodyTracker(); c.resetToPlayer(cardinal);
            near(c.getEstimatedBodyYaw(), facing, "spawn facing " + facing);
            double angle = Math.toRadians(facing);
            cardinal.x = Math.sin(angle) * 0.2; cardinal.z = -Math.cos(angle) * 0.2;
            c.stepServerTick(cardinal); near(c.getEstimatedBodyYaw(), facing, "backward at " + facing);
        }
        FakePlayer p=new FakePlayer(); p.head=90; p.staleBody=0;
        PlayerBodyTracker t=new PlayerBodyTracker(); t.resetToPlayer(p);
        near(t.getEstimatedBodyYaw(),90,"reset uses facing, not stale server body");
        p.head=120; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),90,"small head-only turn");
        p.head=180; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),130,"large stationary turn follows without stale server body");
        Location event=new Location(A,0,0,0); event.set(A,0,0,0,180);
        for(int i=0;i<25;i++) t.stepFromPacket(p,event);
        near(t.getEstimatedBodyYaw(),130,"duplicate packets do not advance body");
        event.set(A,0,0,0,-60); t.stepFromPacket(p,event);
        near(t.getEstimatedBodyYaw(),130,"preview does not commit simulated yaw");
        near(t.getBodyYaw(),-92,"sharp turn preview with bounded visual lead");
        for(int i=0;i<25;i++) t.stepFromPacket(p,event);
        near(t.getBodyYaw(),-92,"duplicate sharp-turn packets remain stable");
        p.head=0; p.x=0; p.z=0; t.resetToPlayer(p);
        p.z=-0.2; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),0,"walking backwards faces forward");
        p.x=0.2; t.stepServerTick(p); check(Math.abs(t.getEstimatedBodyYaw())>1,"strafing turns body");
        check(Math.abs(PlayerBodyTracker.wrapDegrees(p.head-t.getEstimatedBodyYaw()))<=50,"head/body bound");
        p.forward=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.WALK,"walk mode");
        p.flying=true; t.stepServerTick(p); check(t.getMode()==PlayerBodyTracker.MovementMode.FLY,"flight mode");
        p.flying=false; p.head=179; t.resetToPlayer(p); p.head=-179; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),179,"wrap through 180");
        check(t.getLastTickTurnSpeed()<1,"no full-turn wrap jump");
        p.world=B; p.x=1000; p.z=1000; p.head=60; t.stepServerTick(p);
        near(t.getEstimatedBodyYaw(),60,"world change reset"); check(t.getHorizSpeedBlocksPerTick()==0,"world change speed reset");
        p.x+=100; p.head=-100; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),-100,"teleport reset");
        p.head=30; t.resetToPlayer(p); p.head=80; t.notifyArmSwing(); t.stepServerTick(p); near(t.getEstimatedBodyYaw(),45,"arm swing turns body");
        p.vehicle=true; p.vehicleYaw=120; p.head=120; t.stepServerTick(p); near(t.getEstimatedBodyYaw(),120,"vehicle facing");
        near(t.getBodyYaw(),t.getEstimatedBodyYaw(),"no extrapolation in vehicle");
        p.vehicle=false; p.head=Float.NaN; t.stepServerTick(p); check(Float.isFinite(t.getEstimatedBodyYaw()),"non-finite yaw");

        // Packet previews are visible immediately but must not change the once-
        // per-tick simulation, even when there are many packets in one tick.
        FakePlayer move = new FakePlayer(); move.forward=true; move.left=true; move.right=true;
        PlayerBodyTracker withPackets=new PlayerBodyTracker(), tickOnly=new PlayerBodyTracker();
        withPackets.resetToPlayer(move); tickOnly.resetToPlayer(move);
        move.head=90; move.x=-0.2;
        Location sharp=new Location(A,0,0,0); sharp.set(A,move.x,0,move.z,move.head);
        for(int i=0;i<25;i++) withPackets.stepFromPacket(move,sharp);
        near(withPackets.getEstimatedBodyYaw(),0,"preview does not change the tick state");
        near(withPackets.getBodyYaw(),58,"sharp turn preview with bounded lead");
        withPackets.stepServerTick(move); tickOnly.stepServerTick(move);
        near(withPackets.getEstimatedBodyYaw(),40,"sharp walking turn must not be double-counted");
        near(withPackets.getEstimatedBodyYaw(),tickOnly.getEstimatedBodyYaw(),"packet preview vs tick-only turn");
        near(withPackets.getBodyYaw(),58,"tick render target has same bounded lead");
        // Compare 3.2.9 (52) and 3.2.10 (58) in an idealized two-tick
        // linear transition towards a 40-degree body. This illustrates the
        // lag/overshoot tradeoff, not actual Minecraft network/render timing.
        float oldHalfway = 52f * 0.5f;
        float newHalfway = withPackets.getBodyYaw() * 0.5f;
        check(Math.abs(40f-newHalfway) < Math.abs(40f-oldHalfway),
                "stronger lead reduces first-tick lag in the idealized example");
        check(Math.abs(40f-withPackets.getBodyYaw()) > Math.abs(40f-52f),
                "stronger lead can overshoot more at the end of a transition");
        check(withPackets.getMode()==PlayerBodyTracker.MovementMode.WALK,"W+A+D remains forward walking");
        for (int i=0;i<80;i++) {
            move.head=(i%4==0 ? 179 : i%4==1 ? -179 : i%4==2 ? 35 : -85);
            move.x += i%3==0 ? 0.11 : -0.08;
            move.z += i%2==0 ? 0.12 : -0.07;
            sharp.set(A,move.x,0,move.z,move.head);
            for (int j=0;j<5;j++) withPackets.stepFromPacket(move,sharp);
            withPackets.stepServerTick(move); tickOnly.stepServerTick(move);
            near(withPackets.getEstimatedBodyYaw(),tickOnly.getEstimatedBodyYaw(),"packet independent tick " + i);
            near(withPackets.getBodyYaw(),tickOnly.getBodyYaw(),"packet independent visual tick " + i);
            check(Math.abs(PlayerBodyTracker.wrapDegrees(withPackets.getBodyYaw()-withPackets.getEstimatedBodyYaw())) <= 18.001f,
                    "visual lead capped tick " + i);
            check(Math.abs(PlayerBodyTracker.wrapDegrees(move.head-withPackets.getBodyYaw())) <= 50.001f,
                    "visual target stays within head/body bound tick " + i);
        }
        FakePlayer gradual=new FakePlayer();
        PlayerBodyTracker responsive=new PlayerBodyTracker(); responsive.resetToPlayer(gradual);
        gradual.head=60; responsive.stepServerTick(gradual);
        near(responsive.getEstimatedBodyYaw(),10,"moderate turn body estimate unchanged");
        near(responsive.getBodyYaw(),17.5f,"moderate turn predicts three quarters of the step");
        responsive.stepServerTick(gradual);
        near(responsive.getBodyYaw(),10,"moderate lead clears when the body stops");
        FakePlayer turn=new FakePlayer();
        PlayerBodyTracker reversing=new PlayerBodyTracker(); reversing.resetToPlayer(turn);
        turn.head=90; reversing.stepServerTick(turn);
        near(reversing.getEstimatedBodyYaw(),40,"first sharp turn body estimate");
        near(reversing.getBodyYaw(),58,"first sharp turn uses the faster 18-degree lead");
        Location reverseEvent=new Location(A,0,0,0); reverseEvent.set(A,0,0,0,-90);
        for(int i=0;i<25;i++) reversing.stepFromPacket(turn,reverseEvent);
        near(reversing.getBodyYaw(),-52,"reverse preview is limited without packet accumulation");
        near(reversing.getEstimatedBodyYaw(),40,"reverse preview does not alter tick state");
        turn.head=-90; reversing.stepServerTick(turn);
        near(reversing.getEstimatedBodyYaw(),-40,"reverse tick body estimate");
        near(reversing.getBodyYaw(),-52,"reverse visual lead capped at twelve degrees");
        reversing.stepServerTick(turn);
        near(reversing.getBodyYaw(),-40,"reverse lead clears after stopping");
        reversing.resetToYaw(0); turn.head=0; reversing.stepServerTick(turn);
        turn.head=90; reversing.stepServerTick(turn);
        near(reversing.getBodyYaw(),58,"reset clears reversal history");
        FakePlayer strafe=new FakePlayer();
        PlayerBodyTracker strafing=new PlayerBodyTracker(); strafing.resetToPlayer(strafe);
        Location strafeEvent=new Location(A,0,0,0); strafeEvent.set(A,0.2,0,0,0);
        strafing.stepFromPacket(strafe,strafeEvent);
        near(strafing.getEstimatedBodyYaw(),0,"strafing preview must not advance tick state");
        near(strafing.getBodyYaw(),-45,"movement-aware strafing preview");
        for(int i=0;i<25;i++) strafing.stepFromPacket(strafe,strafeEvent);
        near(strafing.getBodyYaw(),-45,"duplicate strafe previews remain stable");
        strafeEvent.set(A,-0.2,0,0,0); strafing.stepFromPacket(strafe,strafeEvent);
        strafeEvent.set(A,0.2,0,0,0); strafing.stepFromPacket(strafe,strafeEvent);
        near(strafing.getBodyYaw(),-45,"preview depends on final position, not packet count");
        strafe.x=0.2; strafing.stepServerTick(strafe);
        near(strafing.getEstimatedBodyYaw(),-27,"strafe simulation at tick");
        near(strafing.getBodyYaw(),-45,"strafe render target at tick");
        strafing.stepServerTick(strafe);
        near(strafing.getBodyYaw(),-27,"visual lead clears immediately on stop");
        strafe.head=120; strafe.flying=true; strafe.x=0.4; strafing.stepServerTick(strafe);
        near(strafing.getBodyYaw(),strafing.getEstimatedBodyYaw(),"no extrapolation in flight");
        strafe.flying=false; strafe.gliding=true; strafe.head=-120; strafing.stepServerTick(strafe);
        near(strafing.getBodyYaw(),strafing.getEstimatedBodyYaw(),"no extrapolation while gliding");
        strafe.gliding=false; strafe.swimming=true; strafe.head=50; strafing.stepServerTick(strafe);
        near(strafing.getBodyYaw(),strafing.getEstimatedBodyYaw(),"no extrapolation while swimming");
        strafe.swimming=false;
        strafe.world=B; strafe.head=-30; strafing.stepServerTick(strafe);
        near(strafing.getBodyYaw(),-30,"world change clears visual lead");
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
