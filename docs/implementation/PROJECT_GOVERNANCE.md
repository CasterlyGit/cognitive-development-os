# Project governance milestone

## Outcome

GitHub Issues and pull requests are the public source of truth for meaningful
work. The repository now defines focused subsystem-story and bug issue forms, a
verification-oriented pull-request template, a compact label taxonomy, a public
architecture/ADR index, and an issue-linked roadmap.

Labels use four orthogonal namespaces:

- `area:*` — intent, graph, compiler, control plane, or governance;
- `type:*` — feature, bug, or decision;
- `status:*` — ready, blocked, or needs review; and
- `risk:*` — low, medium, or high.

## Verification

```bash
python3 -m unittest discover -v
ruby -e 'require "yaml"; Dir[".github/**/*.yml"].each { |f| YAML.load_file(f) }'
codex-public-guard .
```

Expected: 15 tests pass, every workflow/issue-form YAML file parses, and the
public guard passes.

## Limits

This milestone adds no external tracker, bot, auto-merge rule, runtime adapter,
or permission expansion. Repository labels are GitHub metadata and are not a
substitute for typed product permission objects.
