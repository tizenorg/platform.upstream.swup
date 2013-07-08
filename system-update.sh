#!/bin/bash

function system_update
{

	. /etc/os-release
	rm /system-update

	plymouth update --status="Installing Updates..."

	/usr/bin/swup -a
	if [ "$?" != 0 ]; then
	    echo "Update failed"
	    exit -1
	fi
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

if [[ "$1" = "system" && -f /var/lib/snapshot-restore ]]; then
	system_restore
elif [[ "$1" = "factory" && -f /var/lib/factory-restore ]]; then
	factory_restore
elif [[ "$1" = "update" ]]; then
	system_update
fi

# reboot
/sbin/reboot
