# Project Atlas Architecture

## Architecture

### 1. Concept profile

`art/characters/profiles/*.json` stores an individual design brief, supported
proportion controls, palette, traits, and intended actions. The profile schema
validates shape and values; it does not understand arbitrary prose or sculpt a
mesh from it.

### 2. Example observations and recipe knowledge

`art/characters/recipe_observations/` is the planned dataset of independently
sourced, reviewed examples. Each observation uses
[`atlas-character-observation-v1.schema.json`](specs/atlas-character-observation-v1.schema.json)
and records canonical traits, measurements, explicit structural relationships,
source lineage, rights, and review status. A collection of 100 recipes should
be 100 traceable observations, not 100 derivatives counted as independent
evidence from one source.

The first-pass Blender intake tool writes a technical dossier, a separate
technical triage report, and an unknown-by-default observation draft for
`.blend`, `.glb`, or `.gltf` humanoid sources. The screen is limited to
measurable geometry signals; it does not infer semantic anatomy, decide visual
quality or archetype fit, verify rights, or produce a recipe. No approved
observation dataset or miner exists.

The planned local analysis flow is:

1. Normalize names and aliases to versioned concept IDs.
2. Build a graph of observed regions, traits, and typed relationships.
3. Count co-occurrence and relationship patterns by archetype and context.
4. Emit a versioned *candidate findings* artifact with support, denominator,
   confidence, lift, uncertainty, exclusions, source IDs, and data hashes.
5. Review candidate findings. Only approved findings may be copied into the
   authored character grammar.
6. Compile a new character recipe from the requested concept plus applicable
   approved findings, while preserving optional traits and exceptions.

The planned miner must distinguish statements such as “these appeared together
in 78 of 100 reviewed troll examples” from rules such as “every troll must have
both.” It should not infer a relationship from text similarity alone. An
observation needs normalized fields or a human-reviewed extraction before it
can contribute evidence.

Atlas has three different learning/improvement loops, and they must not be
collapsed into one:

1. **Content learning:** offline patterns from independent, reviewed asset and
   recipe observations. This improves future recipes and asset authoring.
2. **Individual NPC learning:** an NPC updates its memories, beliefs, skills,
   preferences, and relationships from events that NPC experienced or learned
   about. This changes that individual, not the species grammar.
3. **World/system improvement:** creators compare simulation outcomes and
   reviewed play/production results, then propose versioned changes to rules,
   models, or tools. This does not automatically rewrite the live world.

Generated variations, copies, and NPC memories are not independent training
examples for content learning. System-wide rule updates need a separate
evaluation and approval path.

### 3. Authored grammar and recipe compiler

`art/characters/grammars/atlas_character_grammar_v1.json` contains shared
defaults, archetype guidance, and anatomy relationships with review status.
`tools/characters/compile_character_recipe.py` combines an individual profile
with the authored grammar and records input hashes. The compiler currently
does not mine cross-example patterns, and the grammar's prose relations are not
a statistical recipe dataset. Future relation-mining work should add a new
versioned contract rather than silently changing old recipe behavior.

### 3a. Evidence records versus executable model recipes

Recipe knowledge has two related but different data products:

- **Observation records** describe what a particular source actually shows:
  normalized features, measurements, relationships, source rights, lineage,
  review state, and uncertainty. They are evidence inputs; they do not tell a
  builder how to make an asset.
- **Model recipes** describe a reproducible candidate build: requested traits,
  parameter values and their provenance, dimensions and coordinate frame,
  geometry method and topology constraints, component links and transforms,
  material and texture assignments, rig/weight sources, variants, collision,
  LODs, performance budgets, validation limits, and expected outputs.

The full cross-category contract is
[`atlas-model-recipe-v1.schema.json`](specs/atlas-model-recipe-v1.schema.json).
It is contract groundwork: the existing character compiler still emits the
smaller `atlas-character-recipe-v1` artifact, and neither it nor the Blender
generator consumes the full model-recipe document yet. Do not describe a schema
as a functioning build executor.

Each numeric parameter records its value, unit where relevant, range,
`influence_weight`, confidence, origin (`user_required`, authored, observed,
candidate, or approved rule), evidence references, and constraints. Here,
`influence_weight` means how strongly a trait should influence recipe
composition. It is not a vertex-to-bone skinning weight. Recipe weights are
bounded and traceable; a user-required design constraint must not be silently
overridden by a learned association.

The dimensions contract records units, handedness, up/forward axes, origin,
target bounds, named measurements, normalization method, tolerances, and
landmarks in a declared frame. Geometry records the builder and version,
configuration hash, method, optional source mesh hash, resolution targets,
semantic surface regions, connectivity groups, and boundary/manifold policy.
Component records describe required/optional pieces, transforms, attachment
slots, and typed relationships such as `attaches_to`, `covers`, or `supports`.

Materials use explicit shader identifiers, base color, roughness, metallic and
normal scale, plus texture channel, file hash, color space, and resolution.
UV requirements record whether mapping is required, whether it is authored or
generated, overlap policy, and target texel density. Explicit material
assignments map semantic surface regions and components to material IDs.
Rigging records the skeleton and rest-pose contracts, method, maximum influence
count, normalization policy, weight source, and weight-validation constraints.
Actual per-vertex bone indices and weights belong in the exported mesh or a
referenced weight sidecar; they should not be duplicated into a high-level
recipe JSON. Motion requirements record animation clips, action IDs, clip hashes,
root-motion behavior, retarget contract, and review state when animation applies.
Variants map explicit state drivers and ranges to supported asset outputs,
enabling later age-, stress-, damage-, or equipment-driven appearance without
embedding simulation behavior in the mesh.

Collision shapes and local transforms, per-LOD mesh references and screen
thresholds, triangle/material/texture/draw-call/bone budgets, rights and source
lineage, observation-set hashes, learned-rule IDs, validation results, review
evidence, and output checksums complete the reproducibility record. A builder
should reject missing required inputs, incompatible units/frames, unresolved
references, failed hard constraints, or hash mismatches before writing a
release candidate. Soft learned findings can rank or suggest options but cannot
silently relax hard constraints. Category-specific extensions should be
versioned rather than stored as undocumented free-form keys.

### 4. Geometry pipeline

`tools/characters/generate_character_base.py` creates a deterministic
parametric blockout and can measure a front image's silhouette. The image fit
adjusts widths; it does not generate detailed hidden geometry, materials, or a
rig. The earlier Sketchfab Troll calibration and Bing Image Creator references
were removed because reuse rights could not be verified or the source was
unavailable. The licensed Troll Mauler and Blender human-base bundle remain
documented authoring references; neither is accepted Atlas geometry.

The generator now refuses the procedural path unless `--allow-blockout` is
explicit. Its record labels the output `blockout_only`. The base-review tool
does not advance it to rig authoring unless a reviewer confirms that it has
been sculpted into the intended mesh and verifies the complete T-pose in the
refreshed preview. The review record is tied to the preview checksum and only
unlocks rig-authoring work. It does not mark the asset production-ready.

The first character quality milestone is a **geometry-only base mesh**: a
complete, connected, correctly proportioned model in the required
`t_pose_fingers_spread` pose, matching the approved design and passing
structural checks. This first mesh is deliberately unrigged and unskinned: it
does not need an armature, bones, skin weights, or animation. Those are created
later from approved visual markers. It also does not need final materials,
textures, hair, skin detail, or runtime packaging. Those belong to later
stages. The automated
shoulder test is only a topology check; silhouette, hands/wrists, proportions,
and actual T-pose alignment still require review against the reference images.
Acceptance is scoped to the base-mesh/rig-authoring stage, never a finished or
shippable character.

“Perfect” is a quality goal, not a machine-verifiable boolean. For this gate,
mesh approval means the creator accepts the design and the recorded checks
pass: the declared scale and coordinate frame are consistent; the T-pose is
complete; wrists join the arms and hands; required anatomy regions are present
and attached as specified; there are no unexplained floating or missing body
parts; normals and surface continuity meet the category policy; and silhouette
and proportions have been reviewed from the available reference views. Separate
eyes, teeth, or other intentionally distinct surfaces are allowed when their
component relationships are explicitly recorded. A topology report alone does
not establish any of these visual or anatomical judgments.

The intended model pipeline is broader than humanoid meshes. It should manage
asset recipes, source references, geometry, materials, textures, rigs or other
deformation data, animation where applicable, collision/interaction metadata,
LODs, runtime packaging, and provenance for every model category. Each category
will have appropriate validators: a creature needs anatomy and deformation
checks; a building needs scale, collision, and modular-fit checks; an item
needs attachment points and material checks. Shared intake, versioning, review,
and release contracts should surround category-specific generation tools.

Two external sources have been downloaded and inspected as authoring
references: the CC-BY Troll Mauler sculpt and Blender Studio's CC0 human-base
bundle. Their metadata, exact checksums, acquisition command, and limitations
are documented in [`art/characters/sources/README.md`](art/characters/sources/README.md).
They remain in the local ignored source cache and are not runtime assets. The
Troll Mauler has a different crouched design and pose, while the Blender source
is human anatomy; neither has been adopted as the Stone Troll output. The
target's high-quality T-pose geometry remains to be authored and reviewed.

#### Generated candidate review

Recipe Studio keeps each successful build in a unique directory under
`art/characters/pending_models/recipe_studio/<draft-id>/<build-id>/`. Its
Generated Model Review gallery lists those builds, loads each available GLB
for local 3D inspection, and shows build metadata. A **kept for reference**
decision is a local review status, not geometry acceptance or runtime approval.
The confirmed delete action removes only the selected build directory after
server-side identifier, expected-record, and path-containment checks. This UI
does not scan or modify source libraries, other pending-model folders, or
runtime assets.

### 4a. Creator-to-runtime gated character workflow

The intended creator experience starts with a plain-language request from the
project owner, a developer, or later an AI-assisted workflow. The request can
include reference images, target dimensions, must-have traits, exclusions,
style, runtime budget, and intended actions. AI is a recipe author and
constrained assistant; it is not the geometry executor or an approval
authority.

Each stage writes a versioned artifact and advances only after its checks and
review gate pass. A rejected artifact remains available as traceable trial
evidence; fixes create a new revision rather than silently changing the
approved artifact.

1. **Request intake.** Preserve the user's original text and image hashes.
   Record required traits, explicit exclusions, category, scale, coordinate
   frame, use case, and unresolved questions. A single view must not be treated
   as evidence for hidden-side anatomy.
2. **AI recipe proposal.** Given the request, schema, and only approved learned
   findings, an AI can propose a detailed model recipe. The proposal includes
   dimensions, proportions, named landmarks, geometry/topology requirements,
   semantic regions, required components and relations, and constraints. Every
   inferred value carries its source/confidence or is labeled as an assumption.
   Hard user requirements remain hard constraints. The AI cannot promote
   candidate findings into approved rules or write runtime assets.
3. **Recipe validation and planning.** A local deterministic validator checks
   schema, units/coordinate frame, ranges, dependencies, asset rights, and
   conflicts with hard requirements. A compiler resolves approved rules and
   explicit parameter values into a frozen build plan with input/tool hashes.
   Missing essentials return to the creator for clarification; they are not
   silently guessed. Current profile validation and character-recipe
   compilation provide only part of this stage; the full model recipe is not
   yet wired in.
4. **Geometry build.** A versioned Blender/Python builder consumes the frozen
   plan and source assets to create the untextured mesh in
   `t_pose_fingers_spread`. The first deliverable is geometry, not a finished
   textured character. It includes the approved silhouette and proportions,
   a complete body with no detached hands or limb gaps, named regions and
   landmarks, declared units/frame, and geometry/topology reports. Keep this
   output unrigged and unskinned; no armature, bones, skin weights, or animation
   are prerequisites for mesh review. Texture, material, hair, and fine-surface
   detail are not prerequisites here either.
5. **Mesh review and iteration.** Show an interactive Blender preview with
   reference overlays, front/side/back views when available, measurements,
   connected-component diagnostics, and T-pose landmarks. The creator accepts
   or rejects the mesh with a rationale. Rejection sends the request/recipe or
   geometry controls back for a new revision. Approval means only “accepted as
   the base mesh for the next stage”; it does not mean textured, rigged, or
   production-ready.
6. **Texture/material recipe and build.** Once geometry is approved, an AI may
   propose material regions and a texture recipe using the approved mesh,
   design request, compatible approved observations, and material constraints.
   Deterministic local code and Blender tools then create UVs and applicable
   texture channels (for example base color, roughness, normal, and ambient
   occlusion) from authored or procedural inputs. Every map records resolution,
   color space, source/license, seed or parameters, and hash. Texture review is
   separate from geometry approval; a texture failure does not rewrite the
   accepted mesh.
7. **Visual landmark placement.** After appearance review, open a Mixamo-style
   interactive rigging UI that overlays draggable visual marker handles on the
   mesh. The creator can inspect the model from multiple views, place and adjust
   required anchors, mirror paired limbs as a starting point, and approve each
   marker. Anchors include root/pelvis, spine, neck, crown/chin, eyes, shoulders,
   elbows, wrists, hand roots/fingertips, hips, knees, ankles, and feet. A
   future AI assistant may suggest initial positions from mesh analysis and the
   recipe, with per-marker confidence and provenance; creator placement and
   approval remain available for every anchor. Store coordinates in the model
   frame and link the marker artifact to the exact approved mesh hash.
8. **Skeleton generation and skinning.** A deterministic Blender rig builder
   consumes the approved marker artifact and a versioned skeleton template to
   create the armature: bone hierarchy, names, joint positions/orientations,
   and rest pose. It validates scale, axes, joint limits, and required bones
   before producing a rig candidate. Generate or transfer skin weights as a
   separate operation; validate normalization, maximum influences, unweighted
   vertices, and deformation at shoulders, elbows, wrists, fingers, hips, and
   knees. The creator reviews the generated skeleton and deformations before
   rig approval. Markers can seed a rig, but do not alone certify professional
   deformation quality. A mesh or marker change invalidates downstream rig
   review.
9. **Animation.** With an approved rig, retarget licensed clips or build
   authored/procedural clips. Record source/license, rig and retargeter hashes,
   root-motion policy, and clip metadata. Preview contact, balance, clipping,
   deformation, and transitions across required actions. Animation approval is
   distinct from rig approval.
10. **Package and release.** Export category-appropriate runtime assets, verify
    hashes, rights, dimensions, materials, topology, rig/animation contracts,
    LOD/performance budgets, and client loading. Register only the exact
    approved output hashes. The runtime manifest must not point at mutable
    work-in-progress files.
11. **Reviewed learning feedback.** Record what failed or succeeded, with
    request/recipe/build versions, tool settings, source lineage, review
    rationale, and output hashes. A local miner may turn independent reviewed
    examples into candidate findings. Candidates need evidence and human
    approval before they inform future AI recipe proposals. Derived revisions
    are related trials, not independent source examples.

The conceptual stage state is:

```text
request
  -> recipe_draft -> recipe_validated -> mesh_candidate -> mesh_approved
  -> texture_candidate -> texture_approved
  -> landmarks_approved -> rig_candidate -> rig_approved
  -> animation_candidate -> animation_approved -> runtime_candidate
  -> runtime_approved
```

Every arrow is a gate, not an implicit side effect. Each downstream artifact
records the parent artifact IDs and hashes. If a parent changes, dependent
stages become stale and must be rebuilt or re-reviewed. The current code has
profile/recipe validation, procedural blockout generation, human marker editing,
and some asset checks; this end-to-end state machine, AI recipe authoring,
texture builder, AI marker proposals, skeleton generation, and animation
authoring flow remain planned work. AI assistance is optional at every stage:
the same versioned recipe and local tools should be usable by creators without
an AI service. Any AI-proposed recipe values or landmarks must be validated,
traceable to evidence or marked as assumptions, and reviewed before they affect
an accepted artifact.

The long-term update loop is: generate or author a candidate, validate it,
review it in its target game context, record failures and successful changes as
traceable observations, update approved recipes or tools, then generate a new
version. Trial-and-error results must retain inputs, parameters, model/tool
versions, review outcomes, and source lineage. A candidate must not train on
its own derived copies as if they were independent examples, and a model or
recipe must not rewrite approved production assets without a review and
versioned release.

### 5. Appearance driven by world state

Character identity and authored appearance are separate from changing state.
The character definition should describe species-specific appearance
capabilities and rules; the simulation should store age, health, stress
exposure, injuries, grooming, and other supported causes as state with event
history. An appearance resolver maps that state to available mesh, morph,
hair, texture, or material variants while preserving the character's identity
and authored choices.

For example, sustained aging or prolonged stress could increase a human
character's grey-hair value over time. That progression should use an explicit
species/lifespan rule, duration and threshold, and a reversible or irreversible
policy appropriate to the game's biology and story. It should not flip hair
color after one stressful event. Other species may have different visible
aging signs or no hair-graying behavior. The model pipeline must provide the
required hair assets, color controls or variants, supported appearance states,
and testing across lighting and animation. This appearance response is a
design goal; age- and stress-driven appearance changes are not implemented.

### 6. Quality, rigging, and release gates

The existing shoulder topology validator checks that sampled torso and arm
regions connect. It does not establish overall manifoldness, good anatomy,
image fidelity, or deformation quality. Production approval still needs a
suitable high-detail source or sculpt, documented rights, automated mesh
checks, visual review, rig-deformation review, and target-runtime performance
checks. Only reviewed and registered assets belong in runtime manifests.

### 7. Persistent world model and event history

The current local server uses SQLite projections for game state and an
append-only event history for accepted actions and authored world edits. The
ontology and schema registry define entity types, event types, and allowed
relationship directions. Entity and relationship edits retain source,
rationale, actor, and event provenance. Current APIs expose local knowledge,
memory, analytics, reasoning, simulations, policy evaluations, and
human-reviewed decisions. These foundations should remain the shared source of
truth for future agent and economy systems rather than adding unrelated state
stores.

Future entity types should include durable NPC identity, household or faction,
town/city, market, resource, production site, route, and institution as the
game needs them. Projections should be rebuildable from events, and important
updates across inventory, relationships, money, and events should commit
atomically.

### 8. Stateful NPC agents

The goal is to simulate individuals with consistent, persistent behavior, not
to make dialogue that forgets the world after each line. An NPC should have
versioned data for:

- stable personality tendencies, values, skills, background, affiliations, and
  preferred ways of acting;
- changing needs, plans, commitments, fears, hopes, and short- and long-term
  goals;
- emotional state that changes from appraised events and stabilizes over time,
  with personality affecting reactions;
- episodic memories of experienced events, people, places, and conversations,
  plus supported beliefs with sources and confidence;
- a social graph linking NPCs and players through directional, contextual
  relationships such as trust, friendship, kinship, rivalry, debt, and
  reputation;
- a bounded decision policy that chooses actions from what the NPC knows,
  wants, can afford, and is allowed to do.

Personality should shape preferences and responses without forcing one scripted
outcome. Emotions should derive from events and appraisals, not random labels
added only to dialogue. Memories and beliefs need provenance, relevance,
recency, and contradiction handling. Relationship changes should cite the
interactions or information that changed them. Agents must distinguish their
own observations from rumors and world facts.

The agent architecture should be hybrid. Routine schedules, movement,
inventory, and market updates should use predictable simulation rules. Slower,
context-rich choices can use a pluggable reasoning model when enabled and when
the agent has enough time/budget. The reasoning layer receives only the
agent's permitted memories, beliefs, needs, relationships, and current context;
it returns a structured action or dialogue proposal. Authoritative server
rules validate actions before any world change. A deterministic fallback must
keep the game running when reasoning is unavailable, over budget, or invalid.

Separate action selection from dialogue realization so words cannot directly
mutate world state. Any optional language service must be isolated behind an
adapter, have explicit cost/latency and privacy policies, and return proposals
that are checked by the same action rules. NPC memories and personality belong
to individual agents; recipe-pattern learning is a separate offline process.
No autonomous NPC reasoning runtime is implemented yet; current NPC entities
and dialogue are scripted game prototypes.

The eventual agent cycle is: perceive accessible world/event information,
update beliefs and memories with sources, appraise relevant events, update
needs and emotional state, choose among allowed actions using personality and
goals, pass the action through authoritative server validation, then remember
the outcome. A rejected action should not mutate the world. Frequent movement
and animation remain separate from slower thought, relationship, settlement,
and economy ticks so simulating more citizens does not require one expensive
reasoning pass per rendered frame. Agents should have explicit processing and
memory budgets, and important state transitions should be reproducible from
versioned rules and events.

### 9. Town and inter-city economy

The long-term economy is a connected simulation from households and businesses
to towns, cities, and trade routes. A local market should track available
goods, inventories, production inputs and outputs, consumption, labor, prices,
currency flows, and relevant taxes or fees. Producers and households should
have budgets and constraints. A trade network should connect markets through
routes with distance, travel time, capacity, cost, risk, and access rules.

Prices and shortages should emerge from recorded supply and demand under
explicit market rules, rather than being arbitrary global numbers. Production
chains should connect raw resources to processed goods and finished products.
Route disruptions, weather, conflict, policy, and player/NPC actions can affect
availability and trade. A city should not have instant knowledge or supply
from another city; transport and information have delays and costs.

The first economy milestone should simulate a small, inspectable network of
markets and a few goods. It should account for inventory and currency
conservation, transaction atomicity, production constraints, and route
capacity. Run deterministic baseline and candidate simulations against event
history, report evidence and uncertainty, apply policy checks, and require
human review before deploying rule changes. The current `resource_progression`
simulation only replays recorded lumen-reed gathering and beacon attempts; it
is not a market, economy, or behavioral forecast.

Markets, NPCs, and cities should share the same item, currency, route, and event
contracts. An NPC's local knowledge may be incomplete or stale even when the
server has a complete world projection. Agents can negotiate or plan, but
transactions must still pass accounting, inventory, capacity, and policy
checks. A transaction should record its price, quantities, counterparties,
market, and source event so price and supply changes can be explained and
replayed.

### 10. Game client and player relationship loop

The current browser client is a local character sandbox with authoritative
server movement, appearance customization, and a small prototype interaction
loop. The broader plan connects this client to persistent NPC state: players
can meet people, build or damage relationships through actions, exchange goods
and information, and see the world react over time. NPC behavior and economic
changes must be driven by server-side validated events, not client claims.
Durable accounts, public networking, and production multiplayer are not yet
implemented.
