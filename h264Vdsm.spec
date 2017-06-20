Name:		h264-spice
Version:	0.1
Release:	1%{?dist}
Summary:	Support h264 to spice

Group:		Applications/System
License:	GPL
URL:		http://www.baidu.com
Source:         %{name}-%{version}.tar.gz
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
Requires:	vdsm

%description
h264 for spice

%prep
%setup -q -n %{name}-%{version}


%build


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices
cp -f graphics.py $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/
cp -f core.py $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/
cp -f graphics.pyo $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/
cp -f core.pyo $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/
cp -f graphics.pyc $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/
cp -f core.pyc $RPM_BUILD_ROOT/usr/share/vdsm/virt/vmdevices/


%clean
rm -rf %{buildroot}


%post
systemctl restart vdsmd.service

%files
%defattr(-,root,root,-)
/usr/share/vdsm/virt/vmdevices/graphics.py
/usr/share/vdsm/virt/vmdevices/core.py
/usr/share/vdsm/virt/vmdevices/graphics.pyc
/usr/share/vdsm/virt/vmdevices/core.pyc
/usr/share/vdsm/virt/vmdevices/graphics.pyo
/usr/share/vdsm/virt/vmdevices/core.pyo


%changelog
* Tue May 23 2017 lijiejun <lijiejun@jieyung.com> 0.1-1
- Initial package
