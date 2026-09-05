# BBB AutoResearch scientific proposal, {stage} iteration {iteration_id}

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, and the relevant tail of
`{journal_path}`. This stage's mechanical experiment identity is already frozen and fully known to
the harness -- component identity, fixed companion parameters, `raw_spec` construction, candidate
and experiment identity, and the frozen research horizon are all materialized by the supervisor from
session state after you respond. Your job is only the scientific content.

{stage_authority_context}

Write one `bbb_autoresearch_scientific_proposal.v1` at `{result_path}` with exactly these fields:

```
{{
  "contract_version": "bbb_autoresearch_scientific_proposal.v1",
  "session_id": "{session_id}",
  "iteration_id": {iteration_id},
  "hypothesis": "...",
  "question": "...",
  "competing_explanation": "...",
  "values": [ ... ],
  "rationale": "...",
  "expected_information_gain": "..."
}}
```

`values` is a list of candidate numeric values for this stage's one mutable dimension -- entirely
your scientific choice, informed by prior evidence in `{state_path}`/`{journal_path}` for this stage,
if any exists yet. Do not invent, rename, or add any other field -- no `component_id`,
`instance_id`, `parameter_name`, `fixed_parameters`, `raw_spec`, `candidate_id`, `experiment_id`, or
`stage_context`; none of these are yours to author here.

Prefer information-dense batches: batch execution has significant fixed wall-clock overhead, so
include all scientifically useful neighboring values in one proposal rather than splitting them
across small sequential ones. For a new search space, prefer a broad coarse sweep to map the response
topology and discover all potentially meaningful regions, not to select the best sampled point. If
relevant structure reaches a tested boundary and a wider range remains scientifically meaningful,
resolve that boundary before narrowing. Once meaningful regions are localized, refine all supported
or plausibly distinct neighborhoods with denser sampling. Do not narrow around a single extremum
while other plausible regions or unresolved boundaries remain.

You may write declared textual/JSON analysis only under `{analysis_dir}`. Exit after this proposal.

Your job is only to produce the requested proposal artifact. Do not install, repair, extend,
validate, or modify the execution environment. Do not execute an experiment, contact Engine/MDS, or
create/modify any repository file. Contract validation, plan materialization, and experiment
execution belong exclusively to the supervisor. Use only the evidence and tools already available to
you. If something required is unavailable, report that fact in the requested artifact instead of
fixing the environment.
