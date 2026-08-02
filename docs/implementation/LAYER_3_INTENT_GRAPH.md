# Layer 3 — Living intent graph

## Outcome

The control plane projects intent atoms into an append-only living graph with
directed `depends_on` edges, symmetric `conflicts_with` edges, and named
clusters. The projection reconstructs after restart and preserves each atom's
source/lifecycle provenance.

Dependency order is deterministic. New cycles, missing endpoints, self edges,
duplicate nodes/edges, invalid clusters, provenance-changing state syncs, and
unknown event types fail closed. An invalid operation is rejected before append
so it cannot poison valid history; independently corrupted cyclic history is
still detected during rebuild.

## Verification

```bash
python3 -m unittest -v tests.test_graph
python3 -m unittest discover -v
python3 -m examples.layer3_graph_demo
```

Expected: 10 graph tests and 25 total tests pass. The demo rebuilds four atoms,
one dependency, one conflict, and one cluster from a temporary ledger after a
simulated restart, with `external_effects: false`.

## Limits

Relationships are explicitly supplied in this layer; semantic inference of
dependencies and conflicts arrives through later planning policy. The graph
does not schedule work, resolve conflicts, or authorize execution. Cluster
membership may overlap because clusters are views, not exclusive ownership.
