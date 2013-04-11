all:

install:
	install -D -m 755 swup.py ${DESTDIR}/usr/bin/swup
	install -D -m 755 system-update.sh ${DESTDIR}/usr/bin/system-update
	install -D -m 755 tools/updateinfo/updateinfo.py ${DESTDIR}/usr/bin/updateinfo
	install -D -m 644 system-update.service ${DESTDIR}/usr/lib/systemd/system/system-update.service
