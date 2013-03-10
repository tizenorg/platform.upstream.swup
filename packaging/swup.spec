Name:           swup
Version:        0.2
Release:        0
License:        GPL-2.0+
Summary:        Software Update Tool
Url:            http://www.tizen.org
Group:          System/Management
Source:         %{name}-%{version}.tar.bz2
BuildRequires:  systemd
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
rm -f %{buildroot}%{_unitdir}/system-update.target
%install_service system-update.target.wants system-update.service

%files
%defattr(-,root,root)
%{_bindir}/swup
%{_bindir}/system-update
%{_bindir}/updateinfo
%{_unitdir}/system-update.service
#%{_unitdir}/system-update.target
%{_unitdir}/system-update.target.wants/system-update.service

%changelog

