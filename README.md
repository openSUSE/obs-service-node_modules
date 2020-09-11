Build packages using node modules offline.

npm is all set up to download stuff from the internet and hide the
details in the "node_modules" subdirectory.
That's incompatible with the pristine sources approach of rpm and
the fully reproducible, offline builds of SUSE distros.

Fortunately npm leave a clue what it does in package-lock.json.  The
file contains the upstream tarball locations as well as the
directory inside node_modules/

So this tool
- parses package-lock.json
- writes a spec file snippet to list all used tarballs as Source
  line
- writes a space separated file that tells which tarball goes where
  inside node_modules
- downloads all tarballs

How to use
----------

- Build the software locally so npm generates package-lock.json. Can
  use osc build and then osc chroot for that for example.
- Copy package-lock.json next to the spec file.
- run

  ```
  nodejs-tarballs.py -o node_modules.inc --locations node_modules.loc --download
  ```

- Modify the spec file

  ```
  Source97:       package-lock.json
  Source98:       node_modules.loc
  Source99:       node_modules.inc
  %include %{SOURCE99}
  BuildRequires:  nodejs-devel-default
  ```

  then later in the %prep section after %setup

  ```
  cp %{SOURCE97} .
  while read file dirs; do
    for d in $dirs; do
      echo "$file -> $d"
      tar --force-local --one-top-level="$d" --strip-components=1 -xzf "%{_sourcedir}/$file"
    done
  done < %{SOURCE98}
  # here you can also apply patches to stuff in node_modules/
  ```

  finally in %build

  ```
  npm rebuild
  ```

Examples
--------
https://build.opensuse.org/package/show/home:lnussel:branches:systemsmanagement:cockpit:rebuild/cockpit-podman
