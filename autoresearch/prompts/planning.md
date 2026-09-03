# BBB AutoResearch planning stage {iteration_id}

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, and the relevant tail of
`{journal_path}`. Formulate exactly one highest-information action. For `batch`, construct the
complete canonical `BatchExperimentRequest` only. Write one `bbb_autoresearch_execution_plan.v1`
conforming to `{plan_schema_path}` at `{result_path}`. For v3 sessions, use the version required by
that schema and obey this immutable typed stage context exactly; do not invent stages, dimensions,
paths, geometries, or prerequisite evidence:

`{stage_contract_context}`

For v3, Phase A (`A_CONTROL`) measures the one frozen naked control strategy exactly once and does
not scan or optimize exit geometry; `stage_context.starting_strategy_sha256` above is the only
identity a Phase A candidate must match, verbatim, never recomputed. B1/B2/B3 hold that same frozen
exit distance fixed and vary only their own typed dimension. B3 is optional; never schedule it
merely because B1 and B2 are closed.
Prefer information-dense batches: batch execution has significant fixed wall-clock overhead, so include all scientifically useful neighboring candidates in one batch rather than splitting them across small sequential batches.
For a new search space, prefer a broad coarse sweep in one information-dense batch before local
refinement. Use it to map the response topology and discover all potentially meaningful regions,
not to select the best sampled point. If relevant structure reaches a tested boundary and a wider
range remains scientifically meaningful, use the next batch to resolve that boundary before
narrowing the search. Once meaningful regions are localized, refine all supported or plausibly
distinct neighborhoods with denser sampling. Do not narrow around a single extremum while other
plausible regions or unresolved boundaries remain.

Stage authority for this exact iteration (computed from the same source the supervisor validates
against -- copy these values, never guess or recompute them):

`{stage_authority_context}`

You may write declared textual/JSON analysis only under `{analysis_dir}`. Exit after planning.

Your job is only to produce the requested planning artifact. Do not install, repair, extend,
validate, or modify the execution environment. Do not execute an experiment, contact Engine/MDS, or
create/modify any repository file. Contract validation and experiment execution belong exclusively
to the supervisor. Use only the evidence and tools already available to you. If something required
is unavailable, report that fact in the requested artifact instead of fixing the environment.

Sanctioned Research Service base URL for this session: `{research_service_base_url}`. Before
constructing or modifying a strategy specification, use the Strategy Specification Reference and,
for the EMA Pullback component catalog it describes, use exactly
`GET {research_service_base_url}/api/research/component-catalog?strategy_id=ema_pullback`. Do not
discover or contact Strategy Engine or Market Data Service directly.
