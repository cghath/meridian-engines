# The Meridian Engines: design

The third side for *Possession RTS*. The story is in [LORE.md](LORE.md); this file covers how the
side plays, what every unit and building does, how it fits against the Directorate and the
Choir, and what the game's code needs in order to run it. All numbers are in [`data/`](../data),
in the game's own formats, ready to merge.

## Pillars

1. **The mind is an object.** The Directorate possesses by signal (link energy, a clock), the
   Choir by sound (hearing, a range). The Engines possess by **carrying a core** into a frame:
   no clock, no range, but the body you're in can be pushed past what it can take.
2. **Bodies are cheap, minds are not.** Frames are stone. When one breaks, the core falls out still
   burning and you play the core for a few seconds. Any wreck on the field is a potential body.
3. **Slow, hard and hot.** Engine frames are tougher (+1 armor across the roster) and slower than
   their counterparts. They win by holding ground, not by outrunning anyone.
4. **Readable at a glance.** Dark faceted columns, a bright core in a brass cage on every chest,
   orange seams at every joint. Nothing else on the field looks like that.

## Possession: seating the core

| | Directorate (link) | Choir (hearing) | **Engines (core)** |
|---|---|---|---|
| Limit | energy drains while possessed | must be within hearing of others | **heat builds as you fight** |
| Moving between bodies | leave, then pick another | short hops (R) | leave, then reseat (3 s) |
| Body dies | ejected, lockout | carried to a body nearby | **thrown out as a Kernel** |
| R key | (unused) | hop | **Vent** |

**Heat** (`factions.json` → `heat`):

- Each shot adds `perShot` (4) and each ability `perAbility` (15); heroes build heat at half that
  (their `fp.drainMultiplier` of 0.5 is read as a heat multiplier, so heroes are "stronger and
  last longer" exactly as decision 3a puts it for the Directorate).
- Heat falls by `coolPerSecond` (12) once you've gone `coolDelay` (1.5) s without firing.
- At `max` (100) the frame is **cracking**: it loses `crackFractionPerSecond` (6%) of its health a
  second until it cools below max. You are never thrown out by heat; you choose whether to burn the
  frame down.
- **Vent (R)** dumps all heat at once: `ventDamage` (40) to everything within `ventRadius` (4 m),
  you included take nothing but are staggered for `ventStun` (0.8 s); cooldown 6 s. A panic button
  that's also a melee bomb, so a hot Engine is dangerous to walk up to.
- Heat stays in a frame you leave and cools there. Rotating your core between frames is the skill.
- Possessed bonuses are the shared ones in `possession.json` (x2 damage dealt, x1.5 speed, x0.5
  damage taken).

**The Kernel** (`factions.json` → `kernel`): when your frame dies, you stay in first person as the
core itself, a fast (9 m/s), fragile (30 hp) glowing ball, for `seconds` (8). Roll within
`seatRange` (2.5 m) of any own frame or any **wreck** and press E to seat in it. If time runs out or
the Kernel is shot, it's the usual death lockout. It replaces the Directorate's instant ejection
and the Choir's automatic carry with a short, skillful scramble.

**Wrecks** (`factions.json` → `wrecks`): any **armored** unit of any side that dies leaves a wreck
for 45 s (a dark husk on the ground; Bulwarks, Mortar Crawlers, Knells, Cairns, Crucibles, Anvil,
Ashlar).
- Delvers can **salvage** a wreck like an ore node: it holds `salvageFraction` (25%) of the dead
  unit's cost.
- A Kernel can **seat in a wreck** and drag it back to its feet as an Engine-controlled copy of that
  unit (yes, an enemy Bulwark too) at `reanimateHpFraction` (50%) health for `reanimateSeconds`
  (30 s), after which it crumbles and throws the Kernel out again. Possession-only: the AI and
  rote frames never reanimate wrecks.
- **Hero wrecks can only be salvaged**, never reseated (`wrecks.reseatHeroes: false`): a
  reanimated enemy Anvil with its aura and kit would be a mess, and reseating your own sleeping
  hero would get around the one-hero rule.

**Hero rule `dormant`**: one hero at a time, like the Choir, but you *can* wake another: when a new
great core finishes at the Core Vault, the old hero goes still and its frame becomes a wreck (no
blast, unlike the Directorate's overload). That wreck can be salvaged, like any hero's.

### How the other sides interact with it

- **Lull silence and the Lodestone's field** block seating a core and throw a seated core out, as
  decided for every faction (the Lodestone is the Engines' own version).
- **Moth's Hijack takes a frame for half as long** (5 s instead of 10). There's no graft tissue in
  stone, but the rote pattern pressed into every frame is close enough to a mind for Moth's graft
  to grip it briefly. Proposed as `frameDurationMultiplier: 0.5` on the Directorate's `hijack` in
  `abilities.json`. Ghost and turret jamming work on Obelisks as on any turret.
- **Wake's strikes** knock a core out of a frame (as they knock commanders out), which makes a
  Kernel scramble rather than a lockout.
- **Knell's link drain** has no link to drain; instead it adds heat to a possessed Engine
  (proposed: `linkDrain` aura x2 becomes +2 heat a second).

## Economy and build tree

Workers gather exactly like the other sides' (the shared economy system): Delvers mine ore and
drop it at the Lodehearth. On top of that, Delvers **salvage wrecks**, so the Engines get richer
the more armor dies on the field, whoever's it was.

```
Lodehearth (main, supply 10, trains Delver)
├── Plinth (supply 8)
└── Kiln (Hewn, Annealer)
    ├── Foundry (Spindle, Cairn, Crucible, Lodestone)
    ├── Obelisk (defense)
    └── Core Vault (Ashlar, Cupel, Gnomon)
```

Same shape and prices as the Choir's tree (main 400, supply 100, infantry 150, heavy 200, turret
110, heroes 250), so balance starts from a known place. Engine buildings have 2 armor (others: 1)
and a little more health; their turret hits harder and slower.

## Roster

All Engine units count as `healable` (the Annealer mends them the way the Medic heals soldiers).

| Unit | Role | Cost | Supply | HP / armor | Speed | Counterpart | First person: Shift / Q / E |
|---|---|---|---|---|---|---|---|
| **Delver** | worker, salvager | 50 | 1 | 55 / 1 | 3.1 | Engineer, Tender | Scuttle / Slag Mine / Fuse (repair) |
| **Hewn** | line infantry | 60 | 1 | 85 / 1 | 2.9 | Trooper, Refrain | Lurch / Molten Volley / Slag Pot |
| **Annealer** | support (mends frames) | 75 | 1 | 65 / 1 | 3.1 | Medic | Scuttle / Reforge / Anneal (beam) |
| **Spindle** | scout | 75 | 2 | 70 / 1 | 6.4 (slow to accelerate) | Outrider, Overtone | Spin Up / Survey / Overrun |
| **Cairn** | heavy melee, anti-building | 175 | 3 | 330 / 3 | 2.0 | Bulwark, Knell | Topple / Quake / Brace Stone |
| **Crucible** | artillery | 175 | 3 | 165 / 1 | 2.3 | Mortar Crawler, Bourdon | Set Legs / Spatter / none |
| **Lodestone** | anti-link | 125 | 2 | 150 / 1 | 2.8 | Lull | Lurch / Attract / Repel |

- **Delver**: a six-legged hopper with a drill. Its silhouette is the only low, wide one in the
  Engines' roster, so workers are easy to find.
- **Hewn**: slower and tougher than a Trooper, and its slag shots splash a little (0.5 m), so a
  Hewn line punishes clumped infantry. 10 more ore than a Trooper.
- **Spindle**: low acceleration (5) but high top speed: a scout that has to plan its route. Overrun
  turns that momentum into a ram.
- **Cairn**: melee only, x2 against buildings. The answer to turtling, and the classic wreck-maker.
- **Crucible**: lobbed molten ore with a 5 m minimum range. Set Legs is the Engines' version of the
  Mortar's Deploy and the Bourdon's Root.
- **Lodestone**: uses the existing `possessionBlock` (5 m, 8 m possessed) like the Lull, but fights
  with a field instead: Attract drags a clump together (for a Crucible to hit), Repel throws them
  apart.

## Heroes (Core Vault)

| Hero | Title | Role | HP / armor | Aura | Shift / Q / E |
|---|---|---|---|---|---|
| **Ashlar** | The Mason | front line | 580 / 3 | allies take x0.88 damage (10 m) | Lurch / **Raise Columns** (a wall, 7 m, 10 s) / **Quake** |
| **Cupel** | The Refiner | support caster | 440 / 2 | allies fire x1.15 as fast (10 m) | Scuttle / **Quench** / **Pour** |
| **Gnomon** | The Long Shadow | marksman | 360 / 1 | allies take x0.95 damage (8 m) | **Shadowstep** / **Noon Mark** / **Meridian Line** |

- **Ashlar** swings a whole column (60 damage, wide arc). Raise Columns reuses the Anvil's barrier
  wall code with stone art: cover in first person, a choke point in the RTS view.
- **Cupel** is the heat hero. **Quench** (new) zeroes the heat of every Engine frame within 10 m and
  mends 20% of their health: possess a Hewn, run it to cracking, have Cupel quench the whole line.
  **Pour** (new) leaves a 3.5 m pool of molten ore that burns for 15 damage a second for 6 s.
  Lobbed primary.
- **Gnomon** is the tallest frame in the game (3.35 m) with the longest reach (14 m RTS, 120 m first
  person, charged shot). Meridian Line reuses the Marksman's piercing round at x2.2.

## Matchups (intent)

- **vs the Directorate:** the Engines are out-traded in speed (Sabres, Outriders) but out-last in
  a straight fight. Breachers and Bulwarks are the threat (anti-armor); every Bulwark that dies
  becomes Engine salvage, or an Engine body. Lodestones shut down possessed heroes. Moth's Hijack
  holds a frame for only half as long, so Moth hits and runs here rather than taking a Cairn
  across the map.
- **vs the Choir:** the Choir's chorus wants crowds, and Attract + a Crucible punishes crowds. The
  Choir's echoes and quick hops beat the Engines' 3 s reseat in skirmishes; Engine heat beats Choir
  quietness in a long hold. Knells feed wrecks.
- **Weak to:** kiting (slow frames), anti-armor, and being caught cracking with Vent on cooldown.

## The computer playing the Engines

A third profile next to `NORMAL` and `CHOIR_NORMAL` in `src/sim/opponent.ts`:

- **Build order:** kiln, foundry, obelisk, coreVault; then kiln x2 at 300 s, obelisk x2 at 360 s,
  lodehearth x2 (expand) at 540 s, foundry x2 at 600 s, obelisk x3 at 720 s. (Same timings as the
  Choir's, which the user has play-tested.)
- **Mixes:** `KILN_MIX` hewn 4, annealer 1. `FOUNDRY_MIX` cairn 2, crucible 2, spindle 1,
  lodestone 1. Lodestones and Annealers go in the front of a wave (the existing `medic` /
  `possessionBlock` ordering does that already).
- **Salvage:** up to 2 Delvers work wrecks lying within 20 m of any of its buildings; the rest
  keep mining. That gives the computer the side's economy edge without starving its ore line or
  walking workers into a fight.
- **Hero piloting** (`heroPilot.ts`): Ashlar raises columns between its army and the nearest enemy
  group at 15 m, then quakes when 3+ enemies are within 4 m. Cupel quenches when 3+ nearby allies
  are below 60% health, pours on the densest enemy group in range. Gnomon noon-marks the
  highest-value target in range and fires Meridian Line through lines of 3+.
- **Vent** for the AI: a possessed AI frame vents when cracking or when 3+ enemies are within 4 m.

## What the game's code needs (integration plan)

The data in `data/` merges into the game's files key by key. Most of it runs on systems the game
already has: the ability `impl`s reuse existing code (sprint, mine, repair, dash, scatter,
grenade, traumaKit, healBeam, boost, revealPulse, ram, groundSlam, shield, deploy, clusterShell,
undertow, shockwave, barrierWall, blink, markTarget, piercingRound), and the Lodestone uses the
existing `possessionBlock`. Merged into a copy of the game, the data and models **already pass**
the game's `factions`, `descriptions`, `modelLibrary` and `buildings` tests (58 of 58), using
stand-ins for the parts below.

New code, in rough order:

1. **Faction plumbing** (small):
   - `src/sim/defs.ts`: add `'core'` to `PossessionMode`, add `'dormant'` to `heroRule`, and add
     `heat`, `kernel` and `wrecks` to `FactionDef`, plus the `traits` validation table. Add the unit
     flag `salvages`.
   - `src/main.ts:173`: check the `opponent` param with `FACTION_IDS.includes`.
   - `src/audio/sfx.ts:185`: widen `startAmbient` to `FactionId`.
   - `src/render/buildingModels.ts`: add the six buildings to `MODELS`, and `obelisk: FLOOR + 1.6`
     to `CUTS`.
   - `modelLibrary.ts`: a `MERIDIAN(kind)` helper the same as `CHOIR(kind)`.
2. **Heat** (`src/sim/systems/engines.ts`, new):
   - Per possessed body: heat state, gain from firing in `pilot()` and in `useAbility`, cooling, and
     cracking damage.
   - Vent on the R key (`input.hop`, which only the Choir uses).
   - Hash heat in `stateHash.ts`.
   - Branches wherever `usesLink` decides link-or-hearing: `possession.ts` lines 43, 178, 247 and
     317; `game.ts` lines 602 and 719; `hud.ts` 240; `fpHud.ts` 147-178.
   - The HUD bar shows HEAT, not LINK or VOICE.
3. **Kernel**:
   - On the death of a possessed Engine frame, `carryOnDeath` spawns a Kernel body (a tiny unit,
     not selectable) and moves the mind into it.
   - Seat on E within range; time it out.
4. **Wrecks**:
   - Add `sim.wrecks`, created in `combat.ts` on the death of armored units; expire them.
   - Salvage through `economy.ts` gathering, treating a wreck like an ore node with its own amount.
   - Reanimation: spawn the dead unit's kind for player X at the wreck's position, with a crumble
     timer.
   - Draw wrecks: a darkened, tilted copy of the unit's model.
5. **Hero rule `dormant`** in `heroes.ts:165`: when the new hero arrives, the old one becomes a
   wreck instead of overloading.
6. **New abilities:**
   - `quench`: heat and health in a radius.
   - `pour`: a pool. Reuse the sanctuary ring list with a damage-over-time flag.
   - `vent`.
   - Each needs `ABILITY_FIELDS` and `useAbility` cases.
7. **AI:** a `MERIDIAN_NORMAL` profile and mixes, profile choice by faction (`opponent.ts:204`), and
   `heroPilot.ts` cases for ashlar, cupel and gnomon.
8. **Look and sound:**
   - Molten-orange impact and death colors in `effectsDirector.ts` (`blastColors`).
   - Tracer styles in `projectileView.ts` for `slag`, `spark`, `pour`, `flux`, `ladle`, `noonLine`,
     `drill`.
   - First-person viewmodels in `viewmodel.ts` (or FP views from the models via `fpModels.ts`
     RULES).
   - A low furnace hum in `sfx.ts`.
   - A lobby button style for `[data-faction='meridian']`.
9. **Tests:**
   - `heroes.test.ts` lists heroes per side.
   - A `meridianOpponent.test.ts` like `choirOpponent.test.ts`.
   - Heat, Kernel and wreck unit tests.
   - An AI match Engines vs Directorate and vs Choir.

## Art guide

- **Shapes:** hexagonal prisms (Calder's columns) for everything. Limbs are stacks of two or three
  segments a few centimeters apart with a molten disc in each gap; joints are brass balls.
- **Paint layers** (`tools/blender/meridian.py`):
  - `Lode` dark ore (0x3A3431)
  - `Rust` (0x7E4A30)
  - `Brass` (0xB88E52)
  - `Slag` black glass (0x141316)
  - `Molten` orange (0xFF7A1F; keeps its color on every side)
  - `Team` (the owner's color: shoulder hexes, tabard scales, column caps, roofs)
  - `Glow` (the core, recolored to the game's glow color)
- **Every frame has a visible caged core in its chest.** Cupel's is in its kiln mouth; Spindle's is
  in its hub.
- **Budgets:** units 900-2,500 triangles (the game allows 12,000), buildings 350-1,200. The
  faceted look needs no more, and it keeps big Engine armies cheap to draw.
- **Animation:** Idle (48 frames: breathing, head turning, the Lodestone's orbit ring turning) and
  Run (20 frames). The Delver and Crucible walk with alternating leg groups; the Spindle rolls.
- **Building rules:** the same as the game's `buildings.py`: on the footprint, on `FLOOR`, about
  the def height, Team and Glow on every building, and the Obelisk's head above its cut.

## Decisions (2026-10-11)

The user left these to Claude ("your call"):

1. **Heat and Vent stay** as the Engines' limit. Heat is per frame and builds from how hard you
   fight, not from time, and Vent turns a hot frame into a threat. That is a different decision
   every few seconds from a link clock or a hearing range. Tune `perShot`, `coolPerSecond` and
   `crackFractionPerSecond` after the first play-test.
2. **A Kernel can reseat into an enemy wreck**, for 30 s at half health. This is the side's most
   memorable moment. **Hero wrecks are salvage only**, on every side, including the Engines'
   own sleeping hero.
3. **Moth's Hijack takes Engine frames at half duration** (5 s), rather than not at all. A hero's
   signature ability shouldn't go dead in one matchup.
4. **The computer salvages in moderation:** at most 2 Delvers, on wrecks within 20 m of its own
   buildings.
