# Bootstrap a BBB AutoResearch session

Read `autoresearch/program.md`, the domain skill named by the session template, the live component
catalog, and current Research batch/config contracts. Initialize a hypothesis-first baseline
question without importing historical winners or hardcoding old parameter ranges. The first
planning worker writes only the plan named by its prompt; a later fresh interpretation process
writes the scientific iteration result after any supervisor-owned execution;
persistent state is created by `scripts/autoresearch_init.py`, not by editing tracked files.
