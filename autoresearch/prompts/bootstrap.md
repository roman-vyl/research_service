# Bootstrap a BBB AutoResearch session

Read `autoresearch/program.md`, the domain skill named by the session template, the live component
catalog, and current Research batch/config contracts. Initialize a hypothesis-first baseline
question without importing historical winners or hardcoding old parameter ranges. The first worker
still performs exactly one iteration and writes `bbb_autoresearch_iteration.v1`; persistent state is
created by `scripts/autoresearch_init.py`, not by editing tracked files.
