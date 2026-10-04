# Third-party notices

Project Atlas uses the following permissively licensed dependencies. Their full license texts are preserved under [`licenses/`](licenses/).

| Package | Version | Maintainer/credit | Use | License |
| --- | --- | --- | --- | --- |
| Three.js | 0.186.1 | Mr.doob and Three.js contributors ([project](https://github.com/mrdoob/three.js)) | Browser 3D renderer; bundled into `web/game.js` | [MIT](licenses/THREEJS-MIT.txt) |
| PyYAML | 6.x or later compatible release | Kirill Simonov and PyYAML contributors ([project](https://pyyaml.org/)) | Safe parsing of Atlas YAML contracts | [MIT](licenses/PYYAML-MIT.txt) |
| esbuild | 0.28.2 | Evan Wallace and esbuild contributors ([project](https://github.com/evanw/esbuild)) | Build-time JavaScript bundler | [MIT](licenses/ESBUILD-MIT.txt) |

The `@esbuild/*` platform package selected by npm is part of esbuild and is also MIT-licensed. Recheck dependency metadata when versions change. Atlas includes maintainer credits even though the MIT license does not require them. These notices cover software; external model credits are in [`ASSET_ATTRIBUTIONS.md`](ASSET_ATTRIBUTIONS.md). The Three.js bundle retains its upstream attribution in [`web/game.js.LEGAL.txt`](web/game.js.LEGAL.txt).
