# Initially forked from https://git.centos.org/rpms/haproxy/tree/c8
# by Benoit Dolez <bdolez at zenetys.com>

%define major           3.4
%define minor           2

%define haproxy_user    haproxy
%define haproxy_group   %{haproxy_user}
%define haproxy_homedir %{_localstatedir}/lib/haproxy
%define haproxy_confdir %{_sysconfdir}/haproxy
%define haproxy_datadir %{_datadir}/haproxy
%define builddir        %{_builddir}/haproxy-%{version}

# lua-5.3 is bundled for el7 only (el7 lua-devel is 5.1, haproxy 3.4 needs >=5.3)
%define liblua          lua-5.3.6

# el7 (rpm 4.11) lacks %%{build_cflags}/%%{build_ldflags}; provide compatible defaults
%if 0%{?rhel} < 8
%define build_cflags    %{optflags}
%define build_ldflags   %{?__global_ldflags}
%endif

%{!?make_verbose: %define make_verbose 0}

%global source_date_epoch_from_changelog 0
%global _hardened_build 1

Name:           haproxy
Version:        %{major}.%{minor}
Release:        1%{?dist}
Summary:        HAProxy reverse proxy for high availability environments

Group:          System Environment/Daemons
License:        GPLv2+
URL:            http://www.haproxy.org/

Source0:        http://www.haproxy.org/download/%{major}/src/haproxy-%{version}.tar.gz
Source2:        haproxy.cfg
Source3:        haproxy.logrotate
Source4:        haproxy.sysconfig
Source5:        halog.1

# Bundled lua-5.3 used only when building for rhel < 8
Source100:      http://www.lua.org/ftp/%{liblua}.tar.gz
Patch100:       lua-5.3-luaroot.patch

BuildRequires:      gcc
BuildRequires:      make
BuildRequires:      systemd-devel

%if 0%{?rhel} >= 8
BuildRequires:      lua-devel
BuildRequires:      openssl-devel
BuildRequires:      pcre2-devel
BuildRequires:      systemd-rpm-macros
%else
# el7 fallbacks:
#   - lua-devel on el7 is 5.1 -> bundle lua-5.3 (Source100/Patch100)
#   - openssl on el7 is 1.0.2 (no TLS 1.3) -> openssl11 from EPEL
#   - gcc on el7 is 4.8.5 (too old) -> devtoolset-11 from SCL
#   - pcre2 not in el7 base -> pcre 8.x
BuildRequires:      pcre-devel
BuildRequires:      openssl11-devel
BuildRequires:      devtoolset-11-gcc
BuildRequires:      devtoolset-11-gcc-c++
%endif

Requires(pre):      shadow-utils

%{?systemd_requires}

%description
HAProxy is a TCP/HTTP reverse proxy which is particularly suited for high
availability environments. Indeed, it can:
 - route HTTP requests depending on statically assigned cookies
 - spread load among several servers while assuring server persistence
   through the use of HTTP cookies
 - switch to backup servers in the event a main one fails
 - accept connections to special ports dedicated to service monitoring
 - stop accepting connections without breaking existing ones
 - add, modify, and delete HTTP headers in both directions
 - block requests matching particular patterns
 - report detailed status to authenticated users from a URI
   intercepted from the application

%prep
%setup -q -n haproxy-%{version}

%if 0%{?rhel} < 8
# el7: unpack bundled lua-5.3 into the haproxy tree and patch it
%setup -T -D -a 100 -n haproxy-%{version}
cd %{liblua}
%patch100 -p1 -b .lua-path
cd ..
%endif

%build
%if 0%{?rhel} < 8
# el7: activate modern gcc from SCL devtoolset-11 for the whole %%build
. /opt/rh/devtoolset-11/enable

# el7: build bundled lua-5.3 static library
cd %{liblua}/src
%{__make} liblua.a %{?_smp_mflags} SYSCFLAGS="-DLUA_USE_LINUX -fPIC" SYSLIBS="-Wl,-E"
lua_inc="$PWD"
lua_lib="$PWD"
cd ../..
[[ -e $lua_inc/lua.h ]] || exit 1
[[ -e $lua_lib/liblua.a ]] || exit 1

# el7: build haproxy against bundled lua, pcre1 and openssl11 (from EPEL)
%{__make} \
    %{?_smp_mflags} \
    V=%{make_verbose} \
    CPU=generic \
    TARGET=linux-glibc \
    USE_OPENSSL=1 \
    USE_PCRE=1 \
    USE_SLZ=1 \
    USE_LUA=1 \
    USE_PROMEX=1 \
    USE_CRYPT_H=1 \
    USE_LINUX_TPROXY=1 \
    USE_GETADDRINFO=1 \
    USE_SYSTEMD=1 \
    USE_NS=1 \
    USE_KTLS= \
    SSL_INC=/usr/include/openssl11 \
    SSL_LIB=/usr/lib64/openssl11 \
    LUA_INC="$lua_inc" \
    LUA_LIB="$lua_lib" \
    LUA_LIB_NAME=lua \
    CFLAGS="%{build_cflags}" \
    LDFLAGS="%{build_ldflags}"
%else
%{__make} \
    %{?_smp_mflags} \
    V=%{make_verbose} \
    CPU=generic \
    TARGET=linux-glibc \
    USE_OPENSSL=1 \
    USE_PCRE2=1 \
    USE_SLZ=1 \
    USE_LUA=1 \
    USE_PROMEX=1 \
    USE_CRYPT_H=1 \
    USE_LINUX_TPROXY=1 \
    USE_GETADDRINFO=1 \
    USE_SYSTEMD=1 \
    USE_NS=1 \
    CFLAGS="%{build_cflags}" \
    LDFLAGS="%{build_ldflags}"
%endif

%{__make} admin/halog/halog V=%{make_verbose} CFLAGS="%{build_cflags}" LDFLAGS="%{build_ldflags}"
%{__make} -C admin/iprange V=%{make_verbose} OPTIMIZE="%{build_cflags}" LDFLAGS="%{build_ldflags}"
%{__make} -C admin/systemd PREFIX=%{_prefix}

%install
%{__make} install-bin DESTDIR=%{buildroot} PREFIX=%{_prefix} TARGET="linux2628"
%{__make} install-man DESTDIR=%{buildroot} PREFIX=%{_prefix}

%{__install} -p -D -m 0644 admin/systemd/haproxy.service %{buildroot}%{_unitdir}/haproxy.service
%{__install} -p -D -m 0644 %{SOURCE4} %{buildroot}%{_sysconfdir}/sysconfig/haproxy

%{__install} -p -D -m 0644 %{SOURCE2} %{buildroot}%{haproxy_confdir}/haproxy.cfg
%{__install} -p -D -m 0644 %{SOURCE3} %{buildroot}%{_sysconfdir}/logrotate.d/haproxy
%{__install} -p -D -m 0644 %{SOURCE5} %{buildroot}%{_mandir}/man1/halog.1
%{__install} -d -m 0755 %{buildroot}%{haproxy_homedir}
%{__install} -d -m 0755 %{buildroot}%{haproxy_datadir}
%{__install} -d -m 0755 %{buildroot}%{_bindir}
%{__install} -p -m 0755 ./admin/halog/halog %{buildroot}%{_bindir}/halog
%{__install} -p -m 0755 ./admin/iprange/iprange %{buildroot}%{_bindir}/iprange
%{__install} -p -m 0755 ./admin/iprange/ip6range %{buildroot}%{_bindir}/ip6range

for textfile in $(find ./ -type f -name '*.txt'); do
    %{__mv} $textfile $textfile.old
    iconv --from-code ISO8859-1 --to-code UTF-8 --output $textfile $textfile.old
    %{__rm} -f $textfile.old
done

%if 0%{?rhel} < 8
# el7: /usr/bin/python is 2.7 and brp-python-bytecompile chokes on Py3 syntax
# in examples/mptcp-backend.py (f-strings). Match the old fork's behavior and
# keep only .cfg example files under %{haproxy_datadir} on el7.
find ./examples/ -type f ! -name '*.cfg' -delete
find ./examples/ -type d -empty -delete
%endif

find ./examples/ -type f |while read -r; do
    %{__install} -p -D -m 0644 "$REPLY" "%{buildroot}%{haproxy_datadir}/${REPLY#./examples/}"
done

%pre
getent group %{haproxy_group} >/dev/null || \
    groupadd -r %{haproxy_group}
getent passwd %{haproxy_user} >/dev/null || \
    useradd -r -g %{haproxy_user} -d %{haproxy_homedir} \
    -s /sbin/nologin -c "haproxy" %{haproxy_user}
exit 0

%post
%systemd_post haproxy.service

%preun
%systemd_preun haproxy.service

%postun
%systemd_postun_with_restart haproxy.service

%files
%defattr(-,root,root,-)
%doc doc/*
%doc CHANGELOG README.md VERSION
%license LICENSE
%dir %{haproxy_homedir}
%dir %{haproxy_confdir}
%dir %{haproxy_datadir}
%{haproxy_datadir}/*
%config(noreplace) %{haproxy_confdir}/haproxy.cfg
%config(noreplace) %{_sysconfdir}/logrotate.d/haproxy
%{_unitdir}/haproxy.service
%config(noreplace) %{_sysconfdir}/sysconfig/haproxy
%{_sbindir}/haproxy
%{_bindir}/halog
%{_bindir}/iprange
%{_bindir}/ip6range
%{_mandir}/man1/*
