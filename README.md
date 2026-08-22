# EnB Droplist

Earth & Beyond automatic drop logger and community drop database project.

## Release deployment

GitHub Actions deploys the current release files to:

`/public_html/EnB/Download/`

on soulbound.se using the repository secret `SIMPLY_SSH_KEY`.

The public release filenames stay stable:

- `EnB Droplist.zip`
- `version.json`

The desktop app checks `https://soulbound.se/EnB/Download/version.json` for updates.
