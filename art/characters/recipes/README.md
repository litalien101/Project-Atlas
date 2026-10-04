# Character Recipes

This directory holds versioned compiled recipe artifacts. A recipe binds a
reviewed design profile to the versioned grammar used for planning. It is not
an observation, a learned rule, or an accepted asset.

The `mpfb_prototype.json` file is a separate experimental input for the
recipe-driven MPFB builder. It does not use the compiled recipe contract below
and is not an approved character or runtime asset.

Compile a standard project recipe after the character brief has been approved:

```sh
python3 tools/characters/compile_character_recipe.py \
  art/characters/profiles/your_character.json \
  --output art/characters/recipes/your_character_v1.json \
  --allow-draft
```

The compiler records source-profile and grammar hashes. Keep each revision
immutable and distinguish draft rules from reviewed, approved defaults.
