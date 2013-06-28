all:

install:
	install -D -m 755 swup.py ${DESTDIR}/usr/bin/swup
	install -D -m 755 system-update.sh ${DESTDIR}/usr/bin/system-update
	install -D -m 644 system-update@.service ${DESTDIR}/usr/lib/systemd/system/system-update@.service
	install -D -m 644 system-restore.target ${DESTDIR}/usr/lib/systemd/system/system-restore.target
	install -D -m 644 factory-reset.target ${DESTDIR}/usr/lib/systemd/system/factory-reset.target
