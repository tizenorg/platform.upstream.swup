
all:
	install -m 755 swup.py ${DESTDIR}/usr/bin/swup
	install -m 755 tools/updateinfo/updateinfo.py ${DESTDIR}/usr/bin/updateinfo
