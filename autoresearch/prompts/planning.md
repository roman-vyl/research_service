# BBB AutoResearch planning stage {iteration_id}

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, and the relevant tail of
`{journal_path}`. Formulate exactly one highest-information action. For `batch`, construct the
complete canonical `BatchExperimentRequest` only. Write one `bbb_autoresearch_execution_plan.v1`
conforming to `{plan_schema_path}` at `{result_path}`. You may write declared textual/JSON analysis
only under `{analysis_dir}`. Exit after planning.

Your job is only to produce the requested planning artifact. Do not install, repair, extend,
validate, or modify the execution environment. Do not execute an experiment, contact Engine/MDS, or
create/modify any repository file. Contract validation and experiment execution belong exclusively
to the supervisor. Use only the evidence and tools already available to you. If something required
is unavailable, report that fact in the requested artifact instead of fixing the environment.

For canonical research discovery, use only the Research Service API at
`{research_service_base_url}`. For the EMA Pullback component catalog, use
`GET {research_service_base_url}/api/research/component-catalog?strategy_id=ema_pullback`. Do not
discover or contact Strategy Engine or Market Data Service directly.
