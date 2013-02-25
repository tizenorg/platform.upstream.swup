Name:           swup
Version:        0.1
Release:        0
License:        GPL-2.0+
Summary:        Software Update Tool
Url:            http://www.tizen.org
Group:          System/Management
Source:         %{name}-%{version}.tar.bz2
Requires:       deltarpm
Requires:       python-lxml
Requires:       python-yaml
Requires:       python-rpm

%description
Software Update Tool.

%prep
%setup -q

%build

%install
%make_install

%files
%defattr(-,root,root)
%{_bindir}/swup
%{_bindir}/updateinfo

%changelog

