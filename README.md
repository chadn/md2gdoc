# md 2 gdoc

Tool for 2-way sync between md files and google docs.

- Single python file, nothing else needed except Google Cloud config
- Designed to be used by both people and ai agents
- Features are well documented - clearly found, clearly explained, and tested.
- Attempts to support as many markdown features as possible, especially project mgmt ones like todo lists,
  documenting both the supported and the unsupported ones

Not to be confused with [benstein/md2gdoc](https://github.com/benstein/md2gdoc), a one-way uploader of the same
name; [docs/similar.md](docs/similar.md) says how the two differ and coexist.

## Use

```text
uv run --script md2gdoc.py init tasks.md     # create the Doc, write tasks.md.gdoc.json, print the link
uv run --script md2gdoc.py status tasks.md   # which side changed since the last sync
uv run --script md2gdoc.py push tasks.md     # replace the Doc from the file; refused if the Doc moved
uv run --script md2gdoc.py pull tasks.md     # write the Doc's content to the file
uv run --script md2gdoc.py --help            # setup, files, exit codes; --dry-run on every command
```

Setup, once: [docs/setup.md](docs/setup.md). `sync`, the three-way merge, is PT-007.

## Layout

- [md2gdoc.py](md2gdoc.py) - the main tool (this is really all you need)
- [PRIVACY.md](PRIVACY.md) - privacy policy; the link the OAuth consent screen points at
- [chadkit/](chadkit/) - project mgmt from [chadkit.com](https://chadkit.com)
	- [tasks.md](chadkit/tasks.md) - for the `PT-NNN` task list.
	- [language.md](chadkit/language.md) - for defining terms used in this repo.
- [docs/](docs/)
	- [features.md](docs/features.md) - every known feature and its status (planned, built, not possible, etc)
	- [design.md](docs/design.md) - how the script works: API calls, normalizer, merge, push guard
	- [similar.md](docs/similar.md) - what else does this, platform paths and tools on GitHub
	- [setup.md](docs/setup.md) - one-time Google Cloud and OAuth setup
- [tests/](tests/)
	- [fixtures/](tests/fixtures/) - round-trip fixtures through Google's converter; the normalizer's test cases
- [scripts/](scripts/) - repo maintenance
