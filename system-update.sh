#!/bin/bash

. /etc/os-release
rm /system-update

# take btrfs snapshot

# call updater

plymouth update --status="Installing Updates..."

for i in `ls /var/cache/updatemanager/install`; do
	UPDATE=$(echo $i | sed -e 's/^[0-9]*-//')
	mkdir -p /var/cache/zypp/packages/$UPDATE/rpms
	/usr/bin/swup -i  $UPDATE 2>&1 | tee /var/log/system-update.log
	rm /var/cache/updatemanager/install/$i
done

# check update status
# update failed revert to snapshot

# reboot
/sbin/reboot
