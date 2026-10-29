# ElytrixFreakModel 3.2.10 compatibility patch

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
it. In 3.2.6 that correction incorrectly mutated the previous tick's simulation
state: on a turn from 0 to 90 degrees while moving forward, the packet correction
made the next tick report 55 degrees instead of the tick-only result of 40.
Version 3.2.7 keeps the immediate packet-time preview separate from the committed
body yaw, so any number of packets cannot double-advance the simulation. Opposite
input keys cancel for walking-animation detection (W+A+D is still forward). The
3.2.4 binary compatibility fixes remain in place.

Version 3.2.8 also previews one simulation step from cumulative packet movement,
so strafe direction is considered before the next scheduled server tick. Render
rotation receives a visual lead of half the estimated body-yaw change, capped at
12 degrees, while the committed body simulation remains unchanged. The lead is
cleared as soon as the estimate stops turning, reset at teleports and world
changes, and disabled in vehicles, swimming and flight. Two-tick ModelEngine
interpolation is unchanged. The lead is a prediction, not the client's actual
body position: it may overshoot or look worse with some movements or packet
latency. It is an experimental server-only trade-off and needs live verification.

Version 3.2.9 limits that lead to four degrees on a confirmed reversal of the
estimated body turn (ordinary turns retain the 12-degree limit), with a one-degree
noise threshold. Packet previews do not advance the history, and resets clear it.
This reduces predictive overcorrection in the covered reversal test.

Version 3.2.10 increases visual prediction to 0.75 of the latest body step,
capped at 18 degrees on ordinary turns and 12 on reversals. This experimental
trade-off is intended to make the displayed model respond sooner. Its stronger
prediction can overshoot further when turning stops and applies to all viewers,
not just the wearer. Body estimation, packet-preview isolation, two-tick
interpolation and the exclusions for vehicles, swimming and flight are
unchanged. It does not eliminate network delay or prove correct behaviour at
every +/-180 degree turn. The 1.21.10 live client and ModelEngine interpolation
were not available for verification, so no claim of perfect tracking is made.

ModelEngine attaches its display pivots to the player. In 3.2.6 the wing
surfaces are shifted closer without moving the shared bone pivots. In 3.2.9,
three small symmetric feathered shoulder-root elements per side overlap the
existing main wing geometry and extend towards the back. They reuse the existing
wing texture and are children of the existing animated bones, with no new bone
or item-model IDs. Their two scale-2 JSONs and the blueprint are packaged with
the updated resource pack. Animation, culling and two-tick interpolation remain.
This server-side estimate is not guaranteed to match every viewer's actual
client-side animation/interpolation, particularly with latency, flying, swimming,
riding or very fast turns. An actual client/server test is required.

To reproduce, use the unmodified jar from commit
`20e2fa0364e2369316897f19a2d44ed47d0b8d31`, Java 21+ and ECJ (see
`AI_INSTRUCTIONS.txt`), e.g.:

```
git show 20e2fa0364e2369316897f19a2d44ed47d0b8d31:plugins/ElytrixFreakModel.jar > /tmp/freakmodel-3.2.3.jar
JAVA=/path/to/java ECJ=/path/to/ecj.jar tools/freakmodel-fix/build.sh /tmp/freakmodel-3.2.3.jar /tmp/freakmodel-3.2.10.jar
```

The script tests the tracker with minimal Bukkit stubs and checks plugin method
references to both patched classes. Stubs are not packaged. These tests do not
replace in-game testing on Pufferfish 1.21.10 with ModelEngine 4.1.0: check
first- and third-person from the wearer and another player, stationary turns,
forward/backward/sideways movement, flight, mounting, teleports and respawn.

Resource-pack checks: `python3 tools/freakmodel-fix/test/validate_assets.py` and
`python3 tools/freakmodel-fix/test/validate_roots.py`. The 3.2.6 geometry
transformation can be reproduced from the original assets using
`adjust_wings.py`; it is intentionally not idempotent. The 3.2.9 shoulder
additions can be reproduced from the pre-3.2.9 assets with `add_wing_roots.py`;
it is also intentionally not idempotent. The scale/UV checks are offline;
ModelEngine's real parser and a Minecraft client were not run here. Check the
SHA-1 in the RP config after generating. On deployment do not overwrite the
server's live ModelEngine config/cache or unrelated assets.

The narrow `elytrix-freakmodel-patch.zip` contains the plugin, blueprint, two
inner-wing models, resource pack and `deploy/install_wing_patch.sh`, but no live
configuration. The installer verifies payload checksums, backs up the live
files under `/root/elytrix-backups`, changes only the `sha1` field in the live
ElytrixRP config, and leaves ModelEngine's config/cache and other assets alone.
It targets `/root/RW_GRIEF` and `/root/RP` by default. A full server restart is
required. `python3 tools/freakmodel-fix/test/test_install.py` tests installation
in an isolated fixture; it does not exercise a real server.

## Server-generated wing asset sync

The live ModelEngine 4.1.0 output for the pre-3.2.9 blueprint was supplied by
the server operator. The existing portions of the inner-wing JSONs retain that
output, including the omission of zero-width-UV faces. The 3.2.9 root elements
were appended using the same observed scale/UV convention, but have not been
checked with the real generator. The generator reorders elements, so validation
matches cubes by geometry rather than array index. Existing item definitions,
textures, atlas and other pack contents are unchanged.

This is a targeted resource synchronization, not a proven fix for the missing
model cubes. Neither client loading nor the rotation and fit have been verified
in game; a real client test is still necessary. The server's generated feather
models differ only by rounding and GUI display transforms, so they were not
replaced. Runtime ModelEngine config and cache must not be shipped or overwritten.
