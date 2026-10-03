# Character recipes

This directory stores versioned compiled character recipes that are inputs to
geometry build plans. A recipe is a candidate build description, not an
observation and not a learned rule. It must retain its source profile and
grammar hashes. Draft archetype rules are identified in the recipe and require
human review before they can become approved grammar.

Compile or refresh a recipe from its profile with:

```sh
python3 tools/characters/compile_character_recipe.py \
  art/characters/profiles/stone_troll.json \
  --output art/characters/recipes/stone_troll_v1.json \
  --allow-draft
```

The Stone Troll recipe currently uses draft troll proportions. It is an
authored starting point for mesh iteration, not statistical evidence from
independent troll examples. Do not count recipe revisions or generated meshes
as independent source observations.
