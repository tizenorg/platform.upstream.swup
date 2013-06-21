#!/bin/bash

function system_update
{

	. /etc/os-release
	rm /system-update

	plymouth update --status="Installing Updates..."

	for i in `ls /var/cache/updatemanager/install`; do
		UPDATE=$(echo $i | sed -e 's/^[0-9]*-//')
		mkdir -p /var/cache/zypp/packages/$UPDATE/rpms
		/usr/bin/swup -i  $UPDATE 2>&1 | tee /var/log/system-update.log
		rm /var/cache/updatemanager/install/$i
	done

	# check update status
	# update failed revert to snapshot
}

function system_restore
{
	SNAPSHOT=$(cat /var/lib/snapshot-restore)

	rm /var/lib/snapshot-restore

	plymouth update --status="Restoring Snapshot..."
	/usr/bin/snapper undochange ${SNAPSHOT}..0
}

function factory_restore
{
	VERIFY_ID=$(snapper list | tail -n1 | awk '{ print $3 }')
	SNAPSHOT=$(cat /var/lib/factory-restore)

	rm /var/lib/factory-restore

	if [ $SNAPSHOT != $VERIFY_ID ]; then
		echo "Factory reset verification failed"
		return -1
	fi

	plymouth update --status="Restoring Factory Default..."

	for i in $(snapper list | tail -n +3 | awk '{ print $3 }'); do
		if [[ $i == 0 || $i == 1 ]]; then
			continue
		fi

		snapper delete $i
	done

	snapper undochange 1..0
}

if [ -f /var/lib/snapshot-restore ]; then
	system_restore
elif [ -f /var/lib/factory-restore ]; then
	factory_restore
elif [ -e /system-update ]; then
	system_update
fi

# reboot
/sbin/reboot
