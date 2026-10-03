# Third-party notices

Project Atlas uses the following permissively licensed dependencies. Their full license texts are preserved under [`licenses/`](licenses/).

| Package | Version | Use | License |
| --- | --- | --- | --- |
| Three.js | 0.186.1 | Browser 3D renderer; bundled into `web/game.js` | MIT |
| PyYAML | 6.x or later compatible release | Safe parsing of Atlas YAML contracts | MIT |
| esbuild | 0.28.2 | Build-time JavaScript bundler | MIT |

The `@esbuild/*` platform package selected by npm is part of esbuild and is also MIT-licensed. Recheck dependency metadata when versions change. The Three.js bundle retains its upstream attribution in [`web/game.js.LEGAL.txt`](web/game.js.LEGAL.txt).

Potential character authoring references are documented in
[`art/characters/sources/README.md`](art/characters/sources/README.md). Their
large source binaries are not committed; the checksum-pinned downloader places
them in the ignored local source cache. Troll Mauler derivatives require
CC-BY-3.0 attribution. The Blender Studio human-base bundle is CC0-1.0. Neither
source is approved as a runtime character asset.
