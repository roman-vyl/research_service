# Research function porting plan v1

## Requirement: vertical slices
Production functionality SHALL be rebuilt as vertical behavior slices and SHALL NOT be copied as whole mixed-responsibility legacy modules.

## Requirement: seam reuse
Every Strategy-owned legacy call SHALL map to an existing or explicitly revised Strategy Engine HTTP contract before its Research-owned caller is implemented.

## Requirement: disconnected mirror
Production modules SHALL NOT import, dynamically load or execute code from `legacy_source`.
