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

%description
Software Update Tool.

%prep
%setup -q

%build
make %{?_smp_mflags}

%install
%make_install

%files
%defattr(-,root,root)

%changelog

