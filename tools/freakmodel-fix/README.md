# ElytrixFreakModel 3.2.5 compatibility patch

The repository contained a binary-only 3.2.3 jar. Its main plugin class was
compiled against a different `PlayerBodyTracker` and `WornAngelRig` than those
actually packaged. This patch replaces the tracker and adds the missing binary
entry points to the existing rig, without rebuilding the other plugin classes.
The constructor bridge resolves the online player by UUID; its call site checks
that the player is online. The passenger-resync bridge restarts the existing
40-tick resync mechanism after teleports and mount changes.

Version 3.2.4 incorrectly used Paper's server-side `Player.getBodyYaw()` as if
it were the body rendered by a client. It can be stale even as a player turns
or strafes; see https://github.com/PaperMC/Paper/issues/9072. Version 3.2.5
instead estimates client body yaw once per server tick from facing, horizontal
motion and arm swing, and resets the estimate on world changes and teleports.
Small head-only turns do not immediately rotate the body. Repeated packets do
not advance the rotation multiple times. The 3.2.4 binary compatibility fixes
remain in place.

ModelEngine attaches its display pivots to the player, and the original
animation, culling, interpolation, models and resource pack are unchanged.
This server-side estimate is not guaranteed to match every viewer's actual
client-side animation/interpolation, particularly with latency, flying, swimming,
riding or very fast turns. An actual client/server test is required.

To reproduce, use the unmodified jar from commit
`20e2fa0364e2369316897f19a2d44ed47d0b8d31`, Java 21+ and ECJ (see
`AI_INSTRUCTIONS.txt`), e.g.:

```
git show 20e2fa0364e2369316897f19a2d44ed47d0b8d31:plugins/ElytrixFreakModel.jar > /tmp/freakmodel-3.2.3.jar
JAVA=/path/to/java ECJ=/path/to/ecj.jar tools/freakmodel-fix/build.sh /tmp/freakmodel-3.2.3.jar /tmp/freakmodel-3.2.5.jar
```

The script tests the tracker with minimal Bukkit stubs and checks plugin method
references to both patched classes. Stubs are not packaged. These tests do not
replace in-game testing on Pufferfish 1.21.10 with ModelEngine 4.1.0: check
first- and third-person from the wearer and another player, stationary turns,
forward/backward/sideways movement, flight, mounting, teleports and respawn.
