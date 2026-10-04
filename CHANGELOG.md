# Project Atlas Change History

### 2026-10-04 — Reset the character authoring baseline

- Removed the retired character concept, its profiles, recipes, candidate
  meshes, remesh trials, review annotations, and one-off source references.
- Cleared the corresponding source-library catalog entries and local model.
- Replaced the authored concept with a neutral parametric starter profile.
- Removed archetype silhouette priors and made the current generator apply
  explicit profile controls only.
- Kept published Git history unchanged; this working tree records the clean
  authoring baseline going forward.

### 2026-10-04 — Guard MPFB waist fitting

- Record before/after pant vertex, face, and height retention for the curved
  sweater hem fit; stop export if the Boolean removes most of the pants.
- Rebuilt and reviewed the current rear waistband. The `0.05 m` radial cutter
  retains 96.43% of faces and 96.01% of pant height; triangle-pair overlap is
  a review metric, not proof of visible failure.
- Kept the failed shell-subtraction attempt archived with its evidence because
  it removed too much of the pants.
