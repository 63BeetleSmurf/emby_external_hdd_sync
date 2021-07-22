# emby_external_hdd_sync
This script will allow you to have an external/portable hard drive or usb drive sync with an Emby playlist. It will automatically mount the drive when inserted, delete no longer needed films, add new films, unmount the drive and then email you when everything is done.
Simply;
Create a Playlist and add films
Plug in the hard drive or usb drive
Wait for an email to say it is ready to remove.
# Install
Place script in /opt/.
Run "crontab -e".
Add "@reboot /opt/emby_external_hdd_sync.py".
Run "pip install -r requirments.txt" or "apt install python3-pyudev".

Create a new playlist in Emby (if required).
Get drive UUID ("lsblk -o path,uuid").
Populate global varibles.
Reboot so cron can start script.
