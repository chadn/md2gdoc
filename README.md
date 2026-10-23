# md 2 gdoc

Tool for 2-way sync between md files and google docs.

- Single python file, nothing else needed except Google Cloud config
- Designed to be used by both people and ai agents
- Features are well documented - clearly found, clearly explained, and tested.
- Supports the markdown features people use most, especially project mgmt ones like todo lists, documenting both
  the supported and the unsupported ones in [docs/features.md](docs/features.md)

## Install

One file, [md2gdoc.py](md2gdoc.py), for Windows, macOS and Linux with Python 3.11 or later. Pick one way:

```text
curl -O https://raw.githubusercontent.com/chadn/md2gdoc/main/md2gdoc.py    # the one file, then
uv run --script md2gdoc.py --help                                           # uv installs its three dependencies

uv tool install git+https://github.com/chadn/md2gdoc                        # or: the command md2gdoc on PATH
md2gdoc --help

pip install google-api-python-client google-auth-oauthlib google-auth-httplib2   # or: plain Python
python md2gdoc.py --help
```

Then the one-time Google setup in [docs/setup.md](docs/setup.md): a Cloud project of your own, an OAuth client of type
Desktop app, its JSON saved as `client_secret.json` in the profile folder (see Files below). The first command that
needs Google opens a browser once; after that the token refreshes itself and the script runs unattended.

## Usage

```text
md2gdoc init tasks.md      # create the Doc from the file, write tasks.md.gdoc.json, print the link
md2gdoc sync tasks.md      # merge both sides' changes since the last sync: write the file, push the Doc
md2gdoc status tasks.md    # which side changed since the last sync
md2gdoc push tasks.md      # replace the Doc from the file; refused when the Doc changed since the last sync
md2gdoc pull tasks.md      # write the Doc's content to the file; refused when the file changed, unless --force
md2gdoc --help             # all of this, plus the setup steps
```

On every command: `--dry-run` says what would happen and changes nothing; `--account NAME` picks the profile;
`--scope drive.file` (the default) or `--scope drive` chooses the Google scope at a profile's first login. `init`
also takes `--name` (the Doc's title) and `--folder` (a Drive folder id); `pull` takes `--force`.

A conflict, the same line changed differently on both sides, is written to the file between `<<<<<<< api-edited`
(the file's version) and `>>>>>>> hand-edited` (the Doc's); nothing is pushed, and `sync` and `push` exit 2 until it
is resolved.

Exit codes: 0 done; 1 usage, setup or Google error; 2 conflict; 3 refused, the other side changed since the last
sync.

Files:

| File | Where | What |
|---|---|---|
| `FILE.gdoc.json` | next to `FILE` | the state file: Doc id, link, Drive version, both sides' text at the last sync; commit it, so a clone syncs the same Doc |
| `client_secret.json` | `<config>/<account>/` | the OAuth client from your Cloud project; never in a repository |
| `token.json` | `<config>/<account>/` | the cached token, which remembers the scope; never in a repository |

`<config>` is `MD2GDOC_CONFIG_DIR` when set, else `%APPDATA%\md2gdoc` on Windows, else `$XDG_CONFIG_HOME/md2gdoc` or
`~/.config/md2gdoc`. `<account>` is `--account`, else `MD2GDOC_ACCOUNT`, else `default`; a second profile is how one
machine syncs under two Google accounts or two scopes.

Environment variables: `MD2GDOC_CONFIG_DIR`, the config directory; `MD2GDOC_ACCOUNT`, the default profile.

## Layout

- [md2gdoc.py](md2gdoc.py) - the main tool (this is really all you need)
- [pyproject.toml](pyproject.toml) - install plumbing for `uv tool install`; nothing imports it
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
