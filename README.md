Build RPM packages using node modules offline
=============================================

By default, npm download dependencies from `registry.npmjs.org` and
hides the details in the `node_modules` subdirectory. Its job is to
resolve version dependencies and provide it to Node application in such
a way that it satisfied the dependencies and does not conflict with
other dependencies. To be able to build and rebuild a package from
sources, we will need to be able to install and possibly update these
dependencies in a networkless environment like OBS.

When `npm` installs dependencies, it will create a `package-lock.json`
that will contain the entire list of packages that can possible exist in
the `node_modules` directory structure.

The purpose of this tool is to parse `package-lock.json` and prepare all
externally download sources for use by `npm` during `rpmbuild`.

## runtime requirements
`npm 7+` is required to produce `package-lock.json` with
`lockfileVersion:2`

## As OBS service

- Get `package-lock.json` with `localfileVersion: 2`. For example,
  - `npm install --package-lock-only --legacy-peer-deps --ignore-scripts`
    with npm 7+
  - `--legacy-peer-deps` is required to fetch peer dependencies from remote
    locally so they are available during peer resolution in the VM. Without
    this you may get additional warnings during install.
- Make sure to put the `package-lock.json` next to the spec file and
  remove it from the sources. Sources should only have `package.json`,
  even if they ship a compatible `package-lock.json`
- Add the following line to the spec file:
   ```
   %include  %{_sourcedir}/node_modules.spec.inc
   ```
- Create file `_service` with the following content:
  ```
  <services>
    <service name="node_modules" mode="manual">
      <param name="cpio">node_modules.obscpio</param>
      <param name="output">node_modules.spec.inc</param>
      <param name="source-offset">10000</param>
    </service>
  </services>
  ```
- `osc service manualrun`
  - this generates the NPM dependency archive along with its source URLs
- `osc add node_modules.obscpio`
- `osc add node_modules.spec.inc`
- `osc commit`

### Example

  ```
  Source10:       package-lock.json
  Source11:       node_modules.spec.inc
  %include        %{_sourcedir}/node_modules.spec.inc
  BuildRequires:  local-npm-registry

  [...]

  %prep
  %setup
  local-npm-registry %{_sourcedir} install --also=dev

  [...]

  %build
  npm run build
  ```

### Service Parameters

- `input` (optional): The input package-lock.json file to parse. Defaults to `package-lock.json`.
- `output` (optional): The file to write RPM source lines into.
- `source-offset` (optional): The RPM source number to start with.
- `legacy-container` (optional): If set to `true`, packages the downloaded files into a `.obscpio` archive (specified by `cpio`). If set to `false` (default), downloads files into a directory specified by `node-dir`.
- `node-dir` (optional): The directory name to store individual tarballs in when `legacy-container` is `false`. Defaults to `node_modules`.
- `cpio` (optional, legacy): The cpio archive filename to store all tarballs in. This parameter can only be used if `legacy-container` is set to `true`.

### In Practice
https://build.opensuse.org/package/show/openSUSE:Factory/cockpit-podman

### External Resources
https://github.com/openSUSE/npm-localhost-proxy
