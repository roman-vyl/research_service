# Config validation cutover

`POST /api/research/config/validate` is now live. Research Service owns draft envelope and execution validation. Strategy Engine owns authoring instance translation and semantic validation. Serialization, saving and selected-config state remain deferred.
