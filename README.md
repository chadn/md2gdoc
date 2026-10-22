# md 2 gdoc

Tool for 2-way sync between md files and google docs.

- Single python file, nothing else needed except Google Cloud config
- Designed to be used by both people and ai agents
- Features are well documented - clearly found, clearly explained, and tested.
- Attempts to support as many markdown features as possible, especially project mgmt ones like todo lists,
  documenting both the supported and the unsupported ones

## Layout

The tool is one file, [md2gdoc.py](md2gdoc.py), at the root (PT-005 wrote its text layer, PT-006 adds the
commands); `scripts/` is repository maintenance, not the tool.

- [docs/design.md](docs/design.md) - how the script works: API calls, normalizer, merge, push guard
- [docs/features.md](docs/features.md) - every known feature and its status
- [docs/similar.md](docs/similar.md) - what else does this, platform paths and tools on GitHub
- [docs/setup.md](docs/setup.md) - one-time Google Cloud and OAuth setup
- [tests/fixtures/](tests/fixtures/) - round-trip fixtures through Google's converter; the normalizer's test cases

## Process

Following [chadkit.com](https://chadkit.com), see [chadkit/](chadkit/) for more, like
[chadkit/tasks](chadkit/tasks.md) for the `PT-NNN` task list.
