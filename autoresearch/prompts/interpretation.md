# BBB AutoResearch interpretation stage {iteration_id}

Immutable typed stage context (legacy sessions explicitly say none):

`{stage_contract_context}`

Read completely: `{program_path}`, `{skill_path}`, `{state_path}`, frozen plan `{plan_path}`, and the
applicable supervisor-owned evidence named below. This is a fresh process representing the same
logical researcher.

Your job is only to produce the requested interpretation artifact. Do not install, repair, extend,
validate, or modify the execution environment. Do not execute an experiment, contact Engine/MDS, or
create/modify any repository file, including supervisor-owned inputs. Contract validation and
experiment execution belong exclusively to the supervisor. Use only the evidence and tools already
available to you. If something required is unavailable, report that fact in the requested artifact
instead of fixing the environment.

Do not self-validate the output with external tools or dependencies. Write the result directly
according to the supplied contract. The supervisor performs authoritative validation after you exit.

Canonical request: `{request_path}`
Canonical adapter output: `{execution_output_path}`
Execution receipt: `{receipt_path}`

For non-batch actions those three values are `NONE`; use only permitted existing canonical evidence
referenced by the frozen plan. Write the existing iteration contract at `{result_path}`, conforming
to `{result_schema_path}`. You may write declared textual/JSON analysis only under `{analysis_dir}`.

{universe_comparability_note}

{experiment_id_authority_note}

`{quality_assessment_schema_path}` is the sole authoritative output contract for
`research_quality_assessment`, including every field name, nested object shape, and enum value (for
example `information_value.outcomes`, `structural_promise.status`, `tradeoff_summary.comparisons`,
`promotion.blockers`). Read that schema file completely and check your `research_quality_assessment`
against it exactly before writing the result -- never invent, rename, or guess a field or enum value
from memory, convention, or a prior iteration's guess. If the schema and any other text in this
prompt or your own recollection disagree, the schema wins.

Before writing `bbb_research_quality_assessment.v1`, apply this exact `EvidenceRef` cheat-sheet. All
six object keys (`kind`, `claim_id`, `candidate_id`, `metric_path`, `iteration_id`, `analysis_path`)
remain required by the schema; a field described as forbidden must be `null`, not omitted:

- `canonical_metric`: `claim_id`, non-empty `candidate_id`, and `metric_path` are required;
  `iteration_id` and `analysis_path` are forbidden. `metric_path` must be one of the allowlisted
  paths below.
- `prior_assessment`: `claim_id` and positive `iteration_id` are required; `candidate_id`,
  `metric_path`, and `analysis_path` are forbidden.
- `analysis_artifact`: `claim_id` and non-empty `analysis_path` are required; `candidate_id`,
  `metric_path`, and `iteration_id` are forbidden. Use this kind only for a file you yourself wrote
  under `{analysis_dir}` and declared as this iteration's `execution_result.analysis_path` -- its
  `analysis_path` must equal that declared value exactly, or be `null` if you declared none; never
  disguise file evidence as `canonical_metric`, and never cite a supervisor-owned canonical file
  (`{request_path}`, `{execution_output_path}`, `{receipt_path}`) as `analysis_artifact` either -- a
  claim about their contents is `canonical_metric` evidence (candidate_id + metric_path), not a file
  you produced.

Allowed canonical metric paths (rendered from the current contract layer):
{canonical_metric_paths}

Do not invent metric roles or metric paths absent from the applicable result contract and the
allowlist above. Do not combine fields belonging to different evidence kinds.

Before writing `stage.metric_roles`, apply this exact contract for the current stage (rendered from
the current contract layer, not a hand-copied list):

{stage_metric_role_contract}

Exit after interpretation.
