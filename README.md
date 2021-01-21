Build RPM packages using node modules offline
=============================================

npm is all set up to download stuff from the internet and hides the
details in the `node_modules` subdirectory.
That's incompatible with the pristine sources approach of rpm and
the fully reproducible, offline builds of SUSE distros.

Fortunately npm leave a clue what it does in `package-lock.json`.  The
file contains the upstream tarball locations as well as the
locations those tarballs need to go inside `node_modules/`

The purpose of this tool is to parse `package-lock.json` and prepare
all externally download sources for use by rpmbuild. There are
several ways the tool can do that.
What all methods have in common is that in the end shell code in
`%prep` has to move all files to the correct locations and call
`npm build` in `%build`. The tool produces a file `node_modules.loc`
to aid that shell code.

## As OBS service

This method runs the download of NPM modules on server side

- Make sure to put the `package-lock.json` next to the spec file.
- Add the following lines to the spec file:
   ```
   # NODE_MODULES BEDIN
   XXX will be filled by script
   # NODE_MODULES END
   ```
- Create file `_service` with the following content:
  ```
  <services>
    <service name="node_modules"/>
  </services>
  ```
- `osc ci`

### Example

  ```
  [...]
  Source:       package-lock.json
  Source:       node_modules.loc
  # NODE_MODULES BEDIN
  # processed by node_modules service
  # NODE_MODULES END
  BuildRequires:  nodejs-devel-default
  BuildRequires:  nodejs-rpm-macros

  [...]

  %prep
  %setup
  cp %{_sourcedir}/package-lock.json .
  %prepare_node_modules %{_sourcedir}/node_modules.loc

  [...]

  %build
  npm rebuild
  ```

## As disabled OBS service

With this method the packager has to call the service locally to
download all NPM modules and bundle them in a cpio archive. The
resulting source rpm has individual sources nevertheless.

A file with `.obscpio` suffix is treated special by OBS and unpacked
automatically by the build script. RPM source lines will be written
to a separate file included at build by rpmbuild (an offset is only
needed for older rpm versions that don't support auto numbering).

- Make sure to put the `package-lock.json` next to the spec file.
- Add the following lines to the spec file:
   ```
   %include node_modules.spec.in
   ```
- Create file `_service` with the following content:
  ```
  <services>
    <service name="node_modules" mode="disabled">
      <param name="cpio">node_modules.obscpio</param>
      <param name="output">node_modules.spec.inc</param>
      <param name="source-offset">10000</param>
    </service>
  </services>
  ```
- `osc ci`

### Example

  ```
  [...]
  Source:       package-lock.json
  Source:       node_modules.loc
  %include      node_modules.spec.in
  BuildRequires:  nodejs-devel-default
  BuildRequires:  nodejs-rpm-macros

  [...]

  %prep
  %setup
  cp %{_sourcedir}/package-lock.json .
  %prepare_node_modules %{_sourcedir}/node_modules.loc

  [...]

  %build
  npm rebuild
  ```


## Manually calling the tool

There are two ways how to list the sources in a spec file

1. write spec file snippet for use with `%include` in some main spec
   file (`--output node_modules.inc`).
   ```
   Source99:       node_modules.inc
   %include %{SOURCE99}
   ```

   This has the advantage to separate the automatically generated
   content from the actual spec file. In OBS several tools do not
   support `%include` statements though.

2. write directly into the spec file (`--spec foo.spec`)
   ```
   # NODE_MODULES BEDIN
   XXX will be filled by script
   # NODE_MODULES END
   ```

Both methods produce source lines without numbers by default. Use e.g.
`--source-offset=1000` to make source lines begin with a specific
offset. Newer RPM versions do not need numbers but OBS may.

There are also several ways how the sources can be downloaded.

1. The simplest way is to let the script download everything into
   the current directory (`--download`), including git checkouts.
   The files have to be managed manually though. Ie this doesn't
   detect no longer used files.
   Use `--download-skip-existing` to avoid redownloading files.

2. Let OBS download the sources by means of the `download_url` and
   `obs_scm` service. Use `--obs-service=_service` for that.

   Sources that are not from npm but git checkouts need some extra
   entries that have to be added manually, eg.
   ```
   <service mode="buildtime" name="tar">
      <param name="obsinfo">RedHatFont.obsinfo</param>
   </service>
   <service mode="buildtime" name="recompress">
     <param name="file">RedHatFont*.tar</param>
     <param name="compression">xz</param>
   </service>
   ```

3. Let OBS download sources with `download_files`. That requires sources to be
   listed in the spec file as `%include` is not supported. So the `_service`
   file needs this:
   ```
     <service name="download_files"/>
   ```

   If the package also has git references, the sources for that can be fetched
   using `obs_scm` like in the previous option. Additionally pass
   `--obs-service-scm-only`.

In addition the script can produce a checksums file as used by Fedora for
verification (`--checksums=FILE`)

### Example

- Build the software locally so npm generates package-lock.json. It's possible
  to prepare the package and run `osc build`. When it failed, reuse the chroot
  to call `npm install` in there.
- Copy package-lock.json next to the spec file.
- run

  ```
  node_modules.py --locations node_modules.loc --spec cockpit-node_modules.spec --obs-service=_service --obs-service-scm-only --source-offset=1000
  ```

- Modify the spec file

  ```
  [...]
  Source:       package-lock.json
  Source:       node_modules.loc
  # NODE_MODULES BEDIN
  # processed by node_modules service
  # NODE_MODULES END
  BuildRequires:  nodejs-devel-default
  BuildRequires:  nodejs-rpm-macros

  [...]

  %prep
  %setup
  cp %{_sourcedir}/package-lock.json .
  %prepare_node_modules %{_sourcedir}/node_modules.loc

  [...]

  %build
  npm rebuild
  ```


- update the `_service` file to include `download_files` resp services needed
  for handling git files if needed.

### In Practice
https://build.opensuse.org/project/show/home:lnussel:branches:systemsmanagement:cockpit:rebuild
