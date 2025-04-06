Name:    whimse
Version: 0.1
Release: 5%{?dist}
Summary: What Have I Modified in SELinux

License: GPL-3.0-or-later
URL:     https://github.com/JurajMarcin/whimse
Source:  %{url}/archive/v%{version}/whimse-%{version}.tar.gz

BuildRequires: python3-devel

Requires: cildiff%{?_isa} = %{version}-%{release}
Requires: dnf
Requires: policycoreutils
Requires: python3-audit
Requires: rpm

%description
WhimSE (or What Have I Modified in SELinux Policy) helps you find modifications
in your SELinux Policy that you have no reasonable explanation for because they
are not from your Linux distribution.


%package -n cildiff

Summary: Diff two CIL SELinux policies.

BuildRequires: gcc
BuildRequires: make
BuildRequires: flex
BuildRequires: gnupg2
BuildRequires: bzip2-devel
BuildRequires: openssl-devel

%description -n cildiff
cildiff is a helper application that compares two CIL SELinux policies.


%prep
%autosetup -p1 -n whimse-%{version}


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel

%set_build_flags
%make_build -C cildiff/selinux/libsepol/src libsepol.a
%make_build -C cildiff VERSION=%{version}


%install
%pyproject_install
%make_install -C cildiff VERSION=%{version}

%pyproject_save_files -L whimse


%files -f %{pyproject_files}
%doc README.md
%license LICENSE
%{_bindir}/whimse


%files -n cildiff
%license LICENSE
%{_bindir}/cildiff


%changelog
* Sat Apr 05 2025 Juraj Marcin <juraj@jurajmarcin.com> - 0.1-5
- Initial prerelase
