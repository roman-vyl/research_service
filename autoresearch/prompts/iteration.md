# BBB AutoResearch iteration {iteration_id}

READ, in this order and completely:

1. `{program_path}`
2. `{skill_path}` (authoritative domain research policy)
3. `{state_path}`
4. the relevant tail of `{journal_path}`
5. only current canonical code/contracts required for this iteration

THEN perform exactly one autonomous research iteration. Do not ask the user for approval. Execute
an experiment only when the hypothesis and information gain justify it. Use the existing canonical
Research batch path through `scripts/autoresearch_execute_batch.py`; validate live catalog/config
semantics before expensive compute. Do not edit tracked source or any file outside
`{iteration_dir}` except canonical artifacts written by the existing application path.

Write the exact structured result required by `{result_schema_path}`
to `{result_path}`. Supplementary analysis may be written only under `{iteration_dir}`. Do not edit
state or journal. Exit after this one iteration; the supervisor will validate, persist continuity,
and launch a fresh context if continuation is warranted.
