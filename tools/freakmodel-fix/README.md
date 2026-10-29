# ElytrixFreakModel 3.2.6 compatibility patch

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
Small head-only turns do not immediately rotate the body. Version 3.2.6 also
applies the bounded body correction directly on sharp move events, rather than
waiting for the next server tick; duplicate packets cannot repeatedly advance
it. The 3.2.4 binary compatibility fixes remain in place.

ModelEngine attaches its display pivots to the player. In 3.2.6 the wing
surfaces are shifted closer without moving the shared bone pivots; the atlas
and two generated wing model JSONs are packaged with the matching blueprint.
The resource pack is shipped along with these assets so the player receives
the matching version. Animation, culling and two-tick interpolation remain.
This server-side estimate is not guaranteed to match every viewer's actual
client-side animation/interpolation, particularly with latency, flying, swimming,
riding or very fast turns. An actual client/server test is required.

To reproduce, use the unmodified jar from commit
`20e2fa0364e2369316897f19a2d44ed47d0b8d31`, Java 21+ and ECJ (see
`AI_INSTRUCTIONS.txt`), e.g.:

```
git show 20e2fa0364e2369316897f19a2d44ed47d0b8d31:plugins/ElytrixFreakModel.jar > /tmp/freakmodel-3.2.3.jar
JAVA=/path/to/java ECJ=/path/to/ecj.jar tools/freakmodel-fix/build.sh /tmp/freakmodel-3.2.3.jar /tmp/freakmodel-3.2.6.jar
```

The script tests the tracker with minimal Bukkit stubs and checks plugin method
references to both patched classes. Stubs are not packaged. These tests do not
replace in-game testing on Pufferfish 1.21.10 with ModelEngine 4.1.0: check
first- and third-person from the wearer and another player, stationary turns,
forward/backward/sideways movement, flight, mounting, teleports and respawn.

Resource-pack checks: `python3 tools/freakmodel-fix/test/validate_assets.py`.
The geometry transformation can be reproduced from the original blueprint,
generated model files and RP using `adjust_wings.py`; it expects unmodified
3.2.3 assets and is intentionally not idempotent. Check the SHA-1 in the RP
config after generating. On deployment do not overwrite the server's live
ModelEngine config/cache or unrelated assets.

## Server-generated wing asset sync

The live ModelEngine 4.1.0 output for the current blueprint was supplied by the
server operator. The two inner-wing JSONs are now the exact generated files,
including the omission of zero-width-UV faces. The generator reorders elements,
so asset validation matches cubes by geometry rather than array index. Existing
item definitions, textures, atlas and other pack contents are unchanged.

This is a targeted resource synchronization, not a proven fix for the missing
model cubes. Neither client loading nor the rotation and fit have been verified
in game; a real client test is still necessary. The server's generated feather
models differ only by rounding and GUI display transforms, so they were not
replaced. Runtime ModelEngine config and cache must not be shipped or overwritten.
