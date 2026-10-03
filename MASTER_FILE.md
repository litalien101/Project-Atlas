# Project Atlas Master File

This is the current source of truth for Project Atlas's vision, architecture,
decisions, and implementation status. It covers the playable world, character
pipeline, recipe learning, NPC behavior, and economy. Update it whenever a
feature, contract, or important design decision changes.

## Vision

Project Atlas should grow into a persistent, believable game world with a
traceable model pipeline for all game assets: people, creatures, clothing,
equipment, props, buildings, environments, resources, and other authored
content. It should learn reusable design knowledge from reviewed examples and
trial outcomes, and support NPCs with persistent identities, personalities,
emotional state, memories, goals, and relationships. Towns and cities should
have connected local economies that respond to production, demand, trade, and
events. Players and NPCs should affect the same auditable world state.

Use local deterministic tools for geometry, recipe analysis, and simulation
where practical; keep human review at quality-sensitive stages; and avoid
spending AI tokens on work ordinary code can do. A single image can guide
visible silhouette and appearance, but it does not contain all the depth,
topology, back-side anatomy, or rigging needed for a production model.

The system should also learn reusable design knowledge from collections of
reviewed character recipes. For example, after reviewing many independent troll
examples, it should be able to propose that certain traits or structural
relationships commonly occur together, show the evidence and uncertainty, and
offer those patterns when composing a new troll recipe. Learned patterns are
recommendations until reviewed; they must not silently become universal anatomy
rules.

## Principles

- Keep concept profiles, observed examples, learned findings, approved grammar
  rules, generated meshes, and runtime assets as separate versioned artifacts.
- Preserve source provenance, licenses, checksums, review state, and rule
  evidence at every stage.
- Separate an observed fact from an inference and an approved rule.
- Count independent examples, not repeated edits or renders of the same source.
- Keep generation and recipe analysis deterministic and local by default. No
  remote model call is required for the planned rule miner.
- Treat a low-detail parametric mesh as a blockout. Do not present it as a
  high-quality model or advance it to rigging without a reviewed sculpt or
  suitable high-detail source.
- Let evidence guide new recipes without forcing every member of an archetype
  into the same design. Preserve exceptions, intentional variation, and
  negative evidence.
- A topology pass is structural evidence, not a visual-quality approval.
- Keep simulation state, observations, beliefs, inferences, and decisions
  distinct. NPCs should not know facts they did not observe, learn, or receive.
- Make world changes replayable and explainable. A simulation result or NPC
  proposal is not a deployed world change until its rules permit it.
- Give each subsystem explicit data contracts, time scales, resource budgets,
  and evaluation gates so large populations can run predictably.

## System map

```mermaid
flowchart LR
  subgraph Offline[Offline authoring and learning]
    Brief[Concept or asset brief] --> Profile[Versioned profile or recipe]
    Examples[Reviewed independent examples] --> Miner[Local pattern miner]
    Miner --> Candidates[Evidence-backed candidate findings]
    Candidates -->|human approval| Grammar[Versioned approved grammar]
    Grammar --> Profile
    Profile --> Builder[Asset-category builder]
    Builder --> QA[Automated checks and human review]
    QA --> Registry[Reviewed versioned asset registry]
  end
  subgraph Live[Live authoritative world]
    Player[Player actions] --> Rules[Server rules]
    Agent[NPC decisions] --> Rules
    Market[Market and travel simulation] --> Rules
    Rules --> Events[Append-only world events]
    Events --> State[SQLite world projections]
    Events --> Memory[NPC memory and relationships]
    State --> Agent
    State --> Market
    Registry --> Visuals[Client model and appearance resolver]
    State --> Visuals
  end
```

Offline recipe learning changes future authored candidates. Live NPC memory
changes individual behavior. The world event stream connects observable actions
and simulation outcomes to both, while review and policy gates control changes
to shared content or live rules.

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
structural checks. It does not need final materials, textures, hair, skin
detail, or runtime packaging. Those belong to later stages. The automated
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
   landmarks, declared units/frame, and geometry/topology reports. Texture,
   material, hair, and fine-surface detail are not prerequisites here.
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
7. **Visual landmark placement.** After appearance review, open the model in a
   marker-placement view. Required anchors can include root/pelvis, spine,
   neck, crown/chin, eyes, shoulders, elbows, wrists, hand roots/fingertips,
   hips, knees, ankles, and feet. A future AI assistant may propose initial
   surface positions by mesh analysis and the recipe, with per-marker confidence
   and provenance. The creator must be able to inspect, drag, and approve every
   marker; a low-confidence or occluded landmark remains a human placement.
   Store marker coordinates in a declared model frame, linked to the exact
   approved mesh hash.
8. **Skeleton and skinning.** A deterministic rig builder maps approved
   landmarks to a versioned skeleton definition, checks bone names/hierarchy,
   rest pose, scale, orientation, and joint limits, then generates or transfers
   skin weights. Validate normalized weights, max influences, empty/unweighted
   vertices, and deformation at representative shoulder, elbow, wrist, finger,
   hip, and knee poses. A mesh/marker change invalidates downstream rig review.
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

## Current status

### Implemented pipeline inventory

- **Profiles and recipes:** `atlas-character-design-profile/v1` has a JSON
  Schema and Python validator. `compile_character_recipe.py` applies the
  authored grammar, scales supported proportions, carries relationships/tags,
  and records profile and grammar hashes. Draft archetype rules require an
  explicit opt-in. Cross-recipe discovery is not connected to this compiler.
- **Full model recipe contract:** `atlas-model-recipe-v1.schema.json` specifies
  cross-category build inputs, dimensions, transforms, materials, rig/weight
  references, UV policy, material assignments, motion clips, variants,
  collision, LOD/performance budgets, provenance, QA, and checksummed outputs.
  It is schema groundwork only; no current generator executes this contract.
- **Prompt-to-recipe orchestration:** Intended workflow is documented in the
  creator-to-runtime section. No AI prompt adapter, recipe drafting service,
  full-contract build-plan compiler, or stage-state orchestrator exists yet.
- **Reference and image tools:** Blender calibration records source metadata,
  measurements, bounds, cross-sections, and rig landmarks. The front-image
  reader extracts a silhouette with local pixel operations and fits width by
  height; it does not infer unseen depth or surface details.
- **Mesh generation and review:** `generate_character_base.py` builds a
  deterministic parametric blockout, semantic body regions, and landmark
  guides. `character_topology.py` analyzes components/boundaries and gates the
  sampled torso-to-shoulder connection. `refresh_character_base_preview.py`,
  `review_character_base.py`, `export_character_markers.py`, and
  `atlas_marker_placement_addon.py` form the preview, human review, and marker
  handoff. The explicit `--allow-blockout` option and sculpt/T-pose review,
  preview checksum, and rig-authoring-only scope prevent an untouched blockout
  from advancing. This gate does not certify production readiness.
- **Geometry acceptance:** Current review tooling requires explicit sculpt and
  T-pose attestations, a passing sampled shoulder-connectivity check, and an
  unchanged preview hash. It does not yet measure the full geometry acceptance
  checklist; complete visual/anatomical review remains human-led.
- **Texture, landmark, rig, and animation stages:** Existing marker guides and
  manual marker-placement UI are a handoff foundation. Texture recipe/build,
  assisted marker placement, a Stone Troll skeleton/weight generator, and its
  animation authoring/approval stages are not implemented. The former raw
  Mixamo clips were removed during the rights audit; no character animations are
  currently registered.
- **Rig and base assets:** No character GLB, rig, or animation clips are
  currently registered. The previous female model, model-derived humanoid rig,
  vest, and raw Mixamo FBXs were removed because their source rights did not
  support retaining those files in the public project repository.
- **Clothing and runtime assets:** Clothing preparation code remains, but its
  former base mesh and body-region map were removed. It is not a usable workflow
  until a licensed replacement mesh and rig pass review. The asset validator
  checks registered paths and checksums, plus GLB skinning when a manifest entry
  supplies its skeleton contract.
- **Appearance persistence:** browser controls can save a validated traveler
  appearance profile through the local server into SQLite. With the prior model
  removed, the profile currently has no registered character mesh to affect;
  hair, age, stress, and emotion do not drive appearance.
- **World persistence and analysis:** ontology-validated entities, relationships,
  actions, and provenance events are stored in SQLite. APIs expose authored
  graph edits, knowledge/memory reads, observed-event analytics, a narrow
  deterministic resource-progression simulation, policy evaluation, and
  human-reviewed decisions. Deployment of policy-approved world changes is
  not implemented.

| Area | Status | Notes |
| --- | --- | --- |
| Design profiles | Implemented | Structured JSON; free-form prompts are not parsed by Blender. |
| Parametric character builder | Implemented as blockout | Not a high-detail sculpt generator. Explicit `--allow-blockout` is required. |
| Front-image measurement | Tool implemented, no retained image data | Use only sources with documented rights; a single view cannot infer depth or production surface detail. |
| Licensed Troll calibration | Not retained | Stale calibration tied to an unavailable source was removed; CC-BY Troll Mauler remains an authoring reference only. |
| Base review gate | Implemented, human-led | Requires sculpt and T-pose attestations; approval unlocks rig work only. |
| Stone Troll geometry-only T-pose base | Not complete | External references are available; neither matches the final design or is accepted as the target mesh. Texturing is a later stage. |
| Recipe compiler | Implemented | Applies authored profile/grammar data; does not learn from a dataset. |
| Cross-category model recipe schema | Contract groundwork | Captures build detail and provenance; builder/compiler integration is not implemented. |
| AI request-to-recipe drafting | Planned | AI may draft structured proposals; deterministic validation and build execution remain required. |
| Geometry-to-texture approval workflow | Planned | Geometry-first order is documented; no general stage-state service or procedural texture builder exists. |
| AI-assisted landmark proposal | Planned | Current Blender add-on supports human placement; suggestions, confidence, and provenance are not implemented. |
| Stone Troll rig and animation pipeline | Not implemented | No character rig or animation clips are currently registered. |
| Structured observation dataset | Contract groundwork | Observation schema and intake guidance are defined; no reviewed dataset has been collected. |
| Relationship discovery/miner | Planned | Recipe curation can run alongside geometry work; do not claim mined findings until the vocabulary and independent licensed dataset support them. |
| Learned-rule approval and recipe composition | Planned | Candidate findings need evidence and human approval before grammar use. |
| Production-quality model generation | Not implemented | Requires a suitable modeling path and high-detail source/sculpt; do not claim the current blockout is production ready. |
| Shared pipeline for every game model category | Not implemented | Character generation and clothing preparation exist; there is no unified generator for props, buildings, environments, and all assets. |
| Age/stress-driven appearance | Not implemented | No simulation state currently changes hair, materials, morphs, or other visual traits over time. |
| Playable world client | Prototype implemented | Browser world/movement sandbox and appearance data persistence; no character model is currently registered after rights cleanup. |
| World graph and history | Local foundation implemented | SQLite entities/relationships and immutable, provenance-bearing events; loopback development API. |
| Analytics and simulation | Narrow prototype implemented | Event counts and one deterministic recorded-event resource-progression counterfactual. |
| NPC personality, emotion, memory, autonomous behavior | Not implemented | Current NPCs and dialogue are scripted prototypes; no persistent agent mind/state yet. |
| Player/NPC and NPC/NPC relationships | Data foundation only | Ontology relationships and event links exist; evolving social relationship behavior is not implemented. |
| Local and inter-city economy | Not implemented | Existing resource progression is not a market or connected economy. |
| Durable accounts and public multiplayer | Not implemented | Current session assignments are local and ephemeral. |

## Documentation index

- [`README.md`](README.md): current project scope, local run instructions,
  browser/runtime assets, APIs, simulations, policy flow, and limits.
- [`specs/atlas-character-generation.md`](specs/atlas-character-generation.md):
  profile, blockout, reference-image, review, marker, and recipe workflow.
- [`specs/atlas-model-recipe-v1.schema.json`](specs/atlas-model-recipe-v1.schema.json):
  versioned technical contract for reproducible cross-category asset recipes.
- [`specs/atlas-character-observation-v1.schema.json`](specs/atlas-character-observation-v1.schema.json)
  and [`art/characters/recipe_observations/README.md`](art/characters/recipe_observations/README.md):
  source evidence and relationship-learning intake, distinct from build recipes.
- [`specs/atlas-character-technical-spec-v1.md`](specs/atlas-character-technical-spec-v1.md):
  runtime character, rig, customization, and equipment contracts.
- [`specs/reach-world-model.md`](specs/reach-world-model.md): current world
  entities, actions, event history, graph, knowledge, memory, and reasoning.
- [`specs/atlas/`](specs/atlas/): ontology, schema registry, event and policy
  contracts used by the local world server.
- [`specs/asset-provenance.md`](specs/asset-provenance.md) and
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md): source, license, and
  redistribution requirements.
- [`art/characters/sources/README.md`](art/characters/sources/README.md):
  checksum-pinned free model references and their licenses/limitations.
- [`specs/local-multiplayer.md`](specs/local-multiplayer.md) and
  [`specs/visual-direction.md`](specs/visual-direction.md): current local
  networking prototype and art-direction goals.

## Roadmap

### Phase A — Stop bad outputs being treated as finished

**Status: safeguards are implemented; the target geometry milestone remains
open.** The milestone is a reviewed geometry-only Stone Troll in a complete
T-pose. It does not require final textures or surface detailing. The previous
browser base was removed during a rights audit; no accepted runtime character
mesh is registered at present.

- Done: procedural output is opt-in and labeled `blockout_only`.
- Done: acceptance fails closed without explicit sculpt and T-pose review; marker
  placement/export requires a checksum-matched review scoped only to rig work.
- Done: the unsuitable Sketchfab Troll calibration, unlicensed Bing reference
  images, and derived measurements were removed; rejected procedural previews
  are removed from active pending-model folders.
- Available for evaluation: pinned CC-BY Troll Mauler and CC0 Blender human
  base references; neither is a target-matching, T-pose Atlas mesh.
- Remaining: build a new Stone Troll geometry source from licensed references
  or original authorship, ensure both hands connect through the wrists and arms,
  pose it to the required T-pose,
  and review proportions/topology before texture/detail authoring.

### Phase B — Stabilize model authoring

- Select a modeling strategy that produces the requested design at useful
  detail: a reviewed authored mesh/sculpt, a validated geometry source, or a
  deterministic generator with enough shape and topology control.
- Validate dimensions, connected body regions, boundaries, normals, materials,
  and source rights before acceptance.
- Add repeatable deformation previews for shoulders, elbows, wrists, hips, and
  knees once a valid rig is available.
- Record visual-review cases, target device budgets, and why a candidate passes
  or fails.
- Generalize shared asset intake, recipe/version records, provenance, QA, and
  runtime registration beyond characters; keep per-category generators and
  validators appropriate to their geometry and use.
- Define an evidence-backed feedback loop for failed and successful asset
  trials, with review before learned changes alter an approved recipe.

### Phase C — Collect normalized recipe evidence

- Define and version canonical trait, anatomy-region, material, and relation
  vocabularies.
- Add one observation per independent reference, with rights and lineage.
- Separate observed presence, explicit absence, unknown, and not applicable.
- Review extracted attributes before they enter the dataset.

### Phase D — Discover and review patterns

- Implement a deterministic local miner for co-occurrence and typed graph
  relationships.
- Stratify results by archetype, style, function, source quality, and other
  relevant context; avoid mixing incompatible groups.
- Report sample support, denominators, uncertainty, provenance, and data hash.
- Evaluate findings on held-out examples and compare against simple baselines.
- Keep findings as candidates until a reviewer approves a versioned rule.

### Phase E — Compose and evaluate new recipes

- Let the compiler use approved rules as weighted suggestions and compatible
  combinations, not mandatory stereotypes.
- Preserve user-specified requirements and allow explicit exceptions.
- Explain which evidence influenced every generated recipe.
- Feed reviewed outcomes back as new observations without treating generated
  variations as independent source evidence.

### Phase F — Stateful NPCs

- Define versioned personality, needs, goals, emotion, memory, belief, and
  relationship contracts.
- Implement local scheduled agent decisions with limited knowledge, explicit
  action policies, and event-sourced outcomes.
- Let player/NPC and NPC/NPC interactions update social relationships with
  evidence and context.
- Evaluate consistency, memory retrieval, relationship changes, bounded
  behavior, and replay determinism before increasing population size.
- Keep dialogue generation separate from authoritative decisions and world
  writes.

### Phase G — Connected regional economy

- Define goods, inventories, producers, consumers, markets, money flows,
  settlements, routes, and institutions as versioned world contracts.
- Build a small local-market simulation first, then connect neighboring
  markets through delayed, capacity-limited routes.
- Add conservation and accounting invariants, policy review, explainable
  counterfactuals, and creator-controlled deployment.
- Let agents participate using their own knowledge, resources, roles, and
  incentives; do not let agents bypass market accounting.

### Phase H — Persistent world operation

- Add durable identities, secure accounts, presence, reconnect behavior, and
  server-driven multiplayer scheduling before exposing sessions remotely.
- Scale NPC and economy update cadence with explicit simulation budgets and
  interest/region scheduling.
- Add operations, backups, migrations, observability, abuse controls, and
  rollback before public deployment.

### Phase I — State-responsive character appearance

- Version the character appearance state separately from identity and base
  asset data.
- Define species-specific aging and prolonged-stress rules, including timing,
  thresholds, persistence, and supported variants.
- Build hair, material, and morph options for supported changes such as gradual
  greying; validate combinations with customization, animation, and lighting.
- Let simulation events update appearance state through explicit rules, then
  resolve to registered runtime assets without generating geometry on every
  frame.

## Decision log

- The unavailable Sketchfab Troll calibration and Bing-generated reference
  images are no longer retained. The pinned CC-BY Troll Mauler and CC0 Blender
  human-base bundle are authoring references only, not the target mesh.
- The base-mesh milestone is geometry-first: a reviewed, design-matched T-pose
  sculpt. It is not a textured or runtime-ready character; surface detail work
  follows geometry acceptance.
- The intended creator pipeline is request -> structured recipe proposal ->
  deterministic recipe validation/build plan -> Blender mesh -> creator geometry
  approval -> texture/material build and approval -> landmark placement and
  approval -> skeleton/skinning -> deformation approval -> animation -> runtime
  packaging. AI can propose recipes and landmark positions but cannot approve
  assets or bypass deterministic checks.
- A free model's license does not make it design-compatible or Atlas-rig
  compatible; downloaded models remain references until independently reviewed.
- A front image is a measurement guide, not a complete 3D asset. Width fitting
  alone cannot solve the model-quality problem.
- Curate target recipes and rights-cleared independent observations in parallel
  with geometry work. The authored Stone Troll recipe is not statistical
  evidence; do not claim mined findings until reviewed independent examples
  exist.
- Implement recipe learning first as an offline Python library/CLI in the
  repository. A separate network service is unnecessary until scale,
  collaboration, or deployment needs justify one.
- Personality and emotion are persistent simulation state with event-based
  causes, not claims that an NPC is conscious.
- The economy is intended to connect household, town, and city systems through
  goods, currency, and constrained trade routes; begin with a small explainable
  simulation rather than a world-wide opaque optimizer.
- The asset pipeline is ultimately shared by every model category and should
  improve through traceable trial results and reviewed recipe revisions.
- Runtime appearance can respond to long-term simulation state, such as gradual
  species-appropriate hair graying from age or prolonged stress; this is not a
  one-event effect or an implemented feature today.

## Notes maintenance

Whenever work changes this plan, update the relevant status and decision above,
then add a dated note with the implemented files and verification performed.
Keep notes factual: mark ideas as proposed, planned, implemented, or blocked;
do not describe a planned stage as working software.

### 2026-10-03 — Generation quality guard

- Added an explicit `--allow-blockout` opt-in and clear default refusal when no
  suitable high-detail source is configured.
- Added a `generation_quality` record and a review acknowledgment required
  before a blockout-derived base can be accepted for rigging.
- Historical note: the Stone Troll calibration was reverted to measurement-only
  and stale generated previews removed. A later rights audit removed the
  unavailable calibration and unverified reference images entirely.
- Checked the profile validator, Python syntax compilation, and diff formatting;
  no full test suite was run.

### 2026-10-03 — Recipe-learning groundwork

- Added the master architecture/decision log and an observation schema for
  independent, rights-traceable character examples.
- Added intake guidance that distinguishes observed presence, explicit absence,
  unknown values, structural relations, and source lineage.
- Recorded recipe relationship mining as deterministic, local, evidence-backed
  candidate discovery that follows model-pipeline stabilization; candidates
  need human approval before entering the authored grammar.
- No dataset or statistical learner was added because there are not yet enough
  independent reviewed observations to support findings.

### 2026-10-03 — Whole-world vision recorded

- Expanded this file to include the current browser/server/world-model
  foundation and distinguish it from the planned living-world systems.
- Recorded the intended persistent NPC model: personality, event-derived
  emotions, bounded memory and beliefs, goals, and evidence-backed relationships
  with players and other NPCs.
- Recorded the intended local-to-regional economy and its inventory, currency,
  production, market, and route constraints, plus the staged roadmap for
  implementation and evaluation.

### 2026-10-03 — Full model-pipeline and evolving-appearance scope

- Expanded the model pipeline vision beyond characters to clothing, equipment,
  props, buildings, environments, resources, and other game models.
- Added a traceable trial/review/update loop so learning comes from documented
  outcomes and does not silently rewrite released content.
- Added state-driven character appearance to the roadmap, including gradual
  age- or prolonged-stress-related greying as a species-specific example.
- Marked shared all-asset generation and dynamic age/stress appearance as not
  implemented so the master file distinguishes vision from current software.

### 2026-10-03 — Project-wide architecture inventory

- Expanded the master file from the character-pipeline roadmap into a project
  architecture covering the implemented browser/server/world foundation, the
  full asset-pipeline goal, NPC agent cycle, and linked market/economy design.
- Separated offline recipe learning, individual NPC adaptation, and creator-led
  system improvement into distinct loops with separate evidence and controls.
- Added a system map and links to the detailed source specifications so this
  file remains the overview rather than replacing their contracts.
- Added the master-file update rule to `AGENTS.md` and linked the overview from
  the project `README.md`.
- Validated the Stone Troll profile, Python syntax, observation JSON Schema,
  and diff formatting. No full test suite was run.

### 2026-10-03 — Technical model-recipe contract

- Added `atlas-model-recipe-v1.schema.json` to describe detailed, reproducible
  build inputs across character, creature, clothing, equipment, prop, building,
  environment, and resource categories.
- Specified units and coordinate frames, dimensions and landmarks, weighted
  recipe parameters with evidence/confidence, geometry and topology settings,
  UV policy and material assignments, component transforms/relationships, PBR
  materials and texture metadata, skeleton/rest-pose and skin-weight
  references, animation clip requirements, state-driven variants,
  collision shapes, LODs, performance budgets, rights/provenance, QA evidence,
  and output hashes.
- Distinguished recipe influence weights from per-vertex skinning weights;
  mesh skin data stays in the model or a hashed sidecar referenced by recipe.
- Updated this architecture to state that the full schema is not yet consumed
  by the existing character compiler or Blender builder.
- Validated schema structure and documentation links; no full test suite was
  run.

### 2026-10-03 — Phase A safeguards and mesh-first acceptance

- Tightened base acceptance to fail closed when the quality tier, T-pose,
  sculpt attestation, connected shoulder core, or explicit non-production state
  is missing. Marker editing/export now requires the checksum-matched
  rig-authoring-only acceptance record.
- Defined the first model milestone as geometry-only: a complete design-matched
  T-pose mesh. Textures, skin detail, materials, and runtime release are later
  stages and do not gate the mesh milestone.
- Downloaded and recorded the CC-BY Troll Mauler source and Blender Studio's
  CC0 Human Base Meshes bundle for local reference. Neither was promoted to the
  Stone Troll asset because each needs design-specific sculpting and T-pose
  review. Large binaries remain in an ignored cache and can be fetched again
  with the pinned downloader.
- The Phase A safeguards are in place, but the target Stone Troll mesh is still
  pending. No finished or production-ready model is claimed.
- Checked pinned file hashes, Python syntax, schema/profile validity, and diff
  formatting; no full test suite was run.

### 2026-10-03 — Staged AI-assisted character authoring design

- Recorded the intended path from a creator's text/images through an AI-proposed
  structured recipe, deterministic validation/build planning, Blender geometry,
  creator mesh approval, texture/material approval, landmark review,
  skeleton/skinning, deformation review, animation, and runtime release.
- Defined downstream artifacts as versioned children of approved inputs; edits
  invalidate dependent approvals. AI may propose recipes or landmark positions
  with evidence/confidence, but deterministic checks and creator approvals
  control stage transitions.
- Set the first success target to a design-matched, connected geometry-only
  Stone Troll in the canonical T-pose. Texturing is intentionally the next
  stage, after creator approval of the mesh.
- Documented that “perfect” is an aspiration translated into visible review
  criteria and structural checks, not an automated pass/fail claim. The current
  checks still cover only shoulder connectivity and provenance-bound review;
  full geometry review remains human-led.
- Reordered the character-generation guide to put texture approval before
  landmark placement, matching the intended workflow. Existing tools do not
  yet enforce the complete stage machine or provide AI recipe/marker services.
- Verified Python syntax, diff formatting, and SHA-256 hashes for the pinned
  reference downloads. No test suite was run.

### 2026-10-03 — Rights audit and asset cleanup

- Removed the female runtime/source model and its textures, underwear archive,
  model-derived rig and body-region records, pending Wayfarer vest, and vest
  workspace because the underlying reuse rights were undocumented.
- Removed the two Bing Image Creator reference images, derived silhouette
  measurements, and stale Troll calibration/comparison records whose source was
  unavailable or whose reuse rights were not verifiable for this project.
- Removed the female-base runtime manifest entry, six raw Mixamo FBX clips, and
  disabled character-model loading in the browser. No character mesh or
  animation clips are registered pending rights-cleared replacements.
- Kept the CC-BY Troll Mauler and CC0 Blender human-base references with their
  pinned checksums and license records. They remain references only.
- Updated the asset validator to check registered paths/checksums and GLB
  skinning when a manifest entry declares its skeleton contract. Updated status
  and clothing documentation to identify base-dependent tools as unusable.
- No measurements from the removed image are retained. Recipe evidence
  collection remains an active parallel task and must use rights-cleared,
  independent examples; the authored Stone Troll profile is a target recipe,
  not learned evidence.
