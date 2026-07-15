# Design

The implementation unit is a vertical behavior slice, not a legacy file. Mixed legacy modules are split along the already-approved Strategy/Research API seam. Strategy semantics are consumed from Strategy Engine; execution, accounting, artifacts and BFF projections are implemented locally from scratch.
