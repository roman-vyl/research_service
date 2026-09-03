# BBB AutoResearch interpretation stage {iteration_id}

Immutable typed stage context (legacy sessions explicitly say none):

`{stage_contract_context}`

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, frozen plan `{plan_path}`, and the
applicable supervisor-owned evidence named below. This is a fresh process representing the same
logical researcher. Do not execute an experiment, contact Engine/MDS, install dependencies, create
runtime substitutes, or modify supervisor-owned inputs.

Canonical request: `{request_path}`
Canonical adapter output: `{execution_output_path}`
Execution receipt: `{receipt_path}`

For non-batch actions those three values are `NONE`; use only permitted existing canonical evidence
referenced by the frozen plan. Write the existing iteration contract at `{result_path}`, conforming
to `{result_schema_path}`. You may write declared textual/JSON analysis only under `{analysis_dir}`.

{experiment_id_authority_note}

Before writing `bbb_research_quality_assessment.v1`, apply this exact `EvidenceRef` cheat-sheet. All
six object keys (`kind`, `claim_id`, `candidate_id`, `metric_path`, `iteration_id`, `analysis_path`)
remain required by the schema; a field described as forbidden must be `null`, not omitted:

- `canonical_metric`: `claim_id`, non-empty `candidate_id`, and `metric_path` are required;
  `iteration_id` and `analysis_path` are forbidden. `metric_path` must be one of the allowlisted
  paths below.
- `prior_assessment`: `claim_id` and positive `iteration_id` are required; `candidate_id`,
  `metric_path`, and `analysis_path` are forbidden.
- `analysis_artifact`: `claim_id` and non-empty `analysis_path` are required; `candidate_id`,
  `metric_path`, and `iteration_id` are forbidden. Use this kind for a file or supplementary
  analysis; never disguise file evidence as `canonical_metric`.

Allowed canonical metric paths (rendered from the current contract layer):
{canonical_metric_paths}

Do not invent metric roles or metric paths absent from the applicable result contract and the
allowlist above. Do not combine fields belonging to different evidence kinds.
Exit after interpretation.
