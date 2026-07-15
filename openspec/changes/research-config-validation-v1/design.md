# Design
Research Service validates draft envelope fields (`config_version`, `experiment_id`, `family`) and execution assumptions. It sends `instances` to Strategy Engine `authoring-config/validate` and maps upstream errors into legacy `{ok, errors:[{path,message}]}`.
