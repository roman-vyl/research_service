# BBB AutoResearch interpretation stage {iteration_id}

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
Exit after interpretation.
