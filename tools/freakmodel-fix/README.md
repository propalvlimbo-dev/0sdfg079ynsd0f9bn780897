# ElytrixFreakModel 3.2.4 compatibility patch

The repository contained a binary-only 3.2.3 jar. Its main plugin class was
compiled against a different `PlayerBodyTracker` and `WornAngelRig` than those
actually packaged. This patch replaces the tracker and adds the missing binary
entry points to the existing rig, without rebuilding the other plugin classes.
The constructor bridge resolves the online player by UUID; its call site checks
that the player is online. The passenger-resync bridge restarts the existing
40-tick resync mechanism after teleports and mount changes.

The tracker reads Paper's actual `Player.getBodyYaw()` instead of independently
simulating body turns on each movement packet. ModelEngine still attaches its
display pivots to the player; its original animation, culling, interpolation,
models, and resource pack are unchanged. Packet events can precede the server's
body update, so the server tick samples it again. Client interpolation/network
latency and differences between the server and client body animation can still
produce visible discrepancies; an actual client/server test is required.

To reproduce, use the unmodified jar from commit
`20e2fa0364e2369316897f19a2d44ed47d0b8d31`, Java 21+ and ECJ (see
`AI_INSTRUCTIONS.txt`), e.g.:

```
git show 20e2fa0364e2369316897f19a2d44ed47d0b8d31:plugins/ElytrixFreakModel.jar > /tmp/freakmodel-3.2.3.jar
JAVA=/path/to/java ECJ=/path/to/ecj.jar tools/freakmodel-fix/build.sh /tmp/freakmodel-3.2.3.jar /tmp/freakmodel-3.2.4.jar
```

The script runs tracker behaviour tests with minimal Bukkit stubs and checks
all plugin method references to the two patched classes. Stubs are
not packaged. These tests do not replace in-game testing on Pufferfish 1.21.10
with ModelEngine 4.1.0: check equip/unequip, stationary and moving turns,
flight, mounting, teleporting between worlds, respawn, and first-person view.
