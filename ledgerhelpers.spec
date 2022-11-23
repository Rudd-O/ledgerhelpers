# See https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_example_spec_file

%define debug_package %{nil}

%define _name ledgerhelpers

%define mybuildnumber %{?build_number}%{?!build_number:1}

Name:           python-%{_name}
Version:        0.3.9
Release:        %{mybuildnumber}%{?dist}
Summary:        A collection of helper programs and a helper library for Ledger (ledger-cli)

License:        GPLv2+
URL:            https://github.com/Rudd-O/%{_name}
Source:         %{url}/archive/v%{version}/%{_name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3

%global _description %{expand:
This is a collection of small single-purpose programs to aid your accounting
with [Ledger](https://github.com/ledger/ledger) (ledger-cli).  Think of it
as the batteries that were never included with Ledger.}

%description %_description

%package -n python3-%{_name}
Summary:        %{summary}

%description -n python3-%{_name} %_description

%prep
%autosetup -p1 -n %{_name}-%{version}

%generate_buildrequires
%pyproject_buildrequires -t


%build
%pyproject_wheel


%install
%pyproject_install

%pyproject_save_files %{_name}


%check
%tox


# Note that there is no %%files section for
# the unversioned python module, python-pello.

# For python3-pello, %%{pyproject_files} handles code files and %%license,
# but executables and documentation must be listed in the spec file:

%files -n python3-%{_name} -f %{pyproject_files}
%doc README.md doc/*


%changelog
* Thu Jun 16 2022 Manuel Amador <rudd-o@rudd-o.com> 0.1.0-1
- First RPM packaging release
