# WhimSE

> **whim** - _noun_  
> a sudden wish or idea, especially one that cannot be reasonably explained

WhimSE (or **W**hat **H**ave **I** **M**odified in **SE**Linux) helps you find
modifications in your SELinux Policy that you have no reasonable explanation
for because they are not from your Linux distribution.

WhimSE scans installed packages for SELinux policies they provide and compares
them with the SElinux policy currently running in your system. All differences
are then summarized in a report formatted to your liking: plain text, HTML, or
JSON. JSON report can be also provided as input and converted to another
format.

## Usage

Fedora/EPEL Repository is available in COPR:
[https://copr.fedorainfracloud.org/coprs/jmarcin/whimse](https://copr.fedorainfracloud.org/coprs/jmarcin/whimse).

For now, only distributions using DNF/RPM are supported.

Simply run `whimse` as root (policy is not readable for ordinary users) and it
will output a plain text report to your terminal. However, the report might get
too long, HTML format is recommended for humans. All options are documented in
help: `whimse --help`.

## Building

WhimSE consists of two programs: WhimSE Python module and CILdiff C program,
which needs to be compiled and installed somewhere in `$PATH`, or the path to
the CILdiff binary needs to be specified using `whimse --cildiff` during
runtime.

CILdiff is statically linked with `libsepol`. The included Makefile compiles it
from the Git submodule in `cildiff/selinux`.

### Building CILdiff

**Build dependencies:**

- `bzip2-devel`
- `openssl-devel`
- `libsepol.a`
  - `flex`
  - `gnupg2`

**Runtime dependencies:**

- `bzip2`
- `openssl`

To build CILdiff, including the `libsepol.a` library:

```sh
# In case the selinux submodule is not downlaoded
# git submodule init && git submodule update
cd cildiff
make
# Optionally, install it
# make install
```

### Building WhimSE

**Runtime dependencies:**

- `dnf`
- `policycoreutils`
- `python3-audit`
- `python3-jinja2`
- `python3-rpm`
- `python3-selinux`
- `python3-setools`
- `rpm`

If you want, you can install it using `pip`, but the Python module can be also run directly:

```sh
pip install .
# or
python -m whimse
```

