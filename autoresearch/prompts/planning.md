# BBB AutoResearch planning stage {iteration_id}

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, and the relevant tail of
`{journal_path}`. Formulate exactly one highest-information action. Do not execute an experiment or
contact Engine/MDS. For `batch`, construct the complete canonical `BatchExperimentRequest` only.
Write one `bbb_autoresearch_execution_plan.v1` conforming to `{plan_schema_path}` at `{result_path}`.
For v3 sessions, use the version required by that schema and obey this immutable typed stage
context exactly; do not invent stages, dimensions, paths, geometries, or prerequisite evidence:

`{stage_contract_context}`

For v3, Phase A measures only configured geometries and does not optimize exits. B3 is optional;
never schedule it merely because B1 and B2 are closed.
You may write declared textual/JSON analysis only under `{analysis_dir}`. Exit after planning.

Sanctioned Research Service base URL for this session: `{research_service_base_url}`. Before
constructing or modifying a strategy specification, use the Strategy Specification Reference and,
for the EMA Pullback component catalog it describes, use exactly
`GET {research_service_base_url}/api/research/component-catalog?strategy_id=ema_pullback`. Do not
discover or contact Strategy Engine or Market Data Service directly.
