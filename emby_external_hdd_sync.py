#!/usr/bin/env python3
#
#  Emby External HHD Sync
#   Populate external hard drive with films from an Emby playlist.
#
#  Copyright 2021 Scott Murphy <scott@murphys.place>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation version 2.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#

# Install
#  Place in /opt/
#  run crontab -e
#  Add "@reboot /opt/emby_external_hdd_sync.py"

import requests
import os
import json
import pyudev
import time
import smtplib, ssl
import yaml

# Source path if different from what emby thinks
#  Such as emby being in container with path mounted to /mnt/Videos/
#  but scrit run outside container using /media/01234/Videos
DRIVE_SOURCE_PATH = '' # Give trailing /
DRIVE_TARGET_UUID = '' # Run "lsblk -o path,uuid" to get it

EMBY_SERVER = ''
EMBY_USER_ID = '' # Go to user and get from URL
EMBY_USER_NAME = ''
EMBY_USER_PASS = ''
EMBY_PLAYLIST_ID = '' # Go to playlist and get from URL
EMBY_HEADERS = {'X-Emby-Authorization': 'Emby UserId="' + EMBY_USER_ID + '", Client="Python", Device="emby_external_hdd_sync", DeviceId="2X4B-523P", Version="0.1"'}

MAIL_SMTP_PORT = 465
MAIL_SMTP_SERVER = ''
MAIL_SENDER = ''
MAIL_RECEIVER = MAIL_SENDER
MAIL_PASSWORD = ''
MAIL_MESSAGE = 'Subject:Emby Playlist Sync Complete\n\nEmby playlist sync is comeplete and the drive can now be removed.'

# Run a system command
def run(command):

    print('Running: ' + command)

    return os.system(command)

def get_mountpoint(uuid):

    for device in json.loads(os.popen('lsblk -Jo path,uuid,mountpoint').read())['blockdevices']:
        if device.get('uuid') == uuid:
            return device.get('mountpoint')

    return None

def mount_partition(dev, uuid):

    mountpoint = get_mountpoint(uuid)

    if mountpoint is not None:
        return mountpoint

    if run('pmount {0} {1}'.format(dev, uuid)) == 0:
        return get_mountpoint(uuid)

    print('Error mounting partition.')
    return False

def unmount_partition(dev, uuid):

    if get_mountpoint(uuid) is not None:
        while run('pumount {0}'.format(dev)):
            print('Waiting to try unmount again...')
            time.sleep(60)

def emby_login():

    r = requests.post(
        EMBY_SERVER + '/emby/Users/AuthenticateByName',
        data={'Username': EMBY_USER_NAME, 'Pw': EMBY_USER_PASS},
        headers=EMBY_HEADERS
        )

    if r.status_code != 200:
        print('Error: ' + str(r.status_code))
        return False

    EMBY_HEADERS['X-Emby-Token'] = r.json()['AccessToken']

    return True

def get_emby_playlist():

    if not emby_login():
        return False

    r = requests.get(
        EMBY_SERVER + '/emby/Playlists/' + EMBY_PLAYLIST_ID + '/Items?Fields=Path',
        headers=EMBY_HEADERS
        )

    if r.status_code != 200:
        print('Error: ' + str(r.status_code))
        return False

    data = {}
    for item in r.json()['Items']:
        data[item['Id']] = item

    return data

def load_target_playlist(target_path):

    if not os.path.isfile(target_path + 'playlist.json'):
        return {}

    with open(target_path + 'playlist.json', 'r') as fh:
        playlist = json.load(fh)

    return playlist

def save_target_playlist(target_path, playlist):

    with open(target_path + 'playlist.json', 'w') as fh:
        json.dump(playlist, fh)

def sync_playlists(target_path):

    source_playlist = get_emby_playlist()
    target_playlist = load_target_playlist(target_path)

    files_to_delete = []
    files_to_copy = []

    # Get files to remove
    for item_id in list(target_playlist):
        if item_id not in source_playlist:
            files_to_delete.append(target_path + target_playlist[item_id]['Path'].split('/')[-1])
            del target_playlist[item_id]

    # Get files to add
    for item_id in source_playlist:
        if item_id not in target_playlist:
            if DRIVE_SOURCE_PATH == '':
                files_to_copy.append(source_playlist[item_id]['Path'])
            else:
                files_to_copy.append(DRIVE_SOURCE_PATH + source_playlist[item_id]['Path'].split('/')[-1])
            target_playlist[item_id] = source_playlist[item_id]

    if len(files_to_delete) or len(files_to_copy):
        run('rm ' + ' '.join(files_to_delete))
        run('cp -t ' + target_path + ' ' +  ' '.join(files_to_copy))
        save_target_playlist(target_path, target_playlist)

def email_notification():

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(MAIL_SMTP_SERVER, MAIL_SMTP_PORT, context=context) as server:
        server.login(MAIL_SENDER, MAIL_PASSWORD)
        server.sendmail(MAIL_SENDER, MAIL_RECEIVER, MAIL_MESSAGE)

def main(args):

    # Load config if available
    config_file = os.path.abspath(os.path.dirname(__file__)) + '/config.yml'
    if os.path.exists(config_file):
        with open(config_file, 'r') as fh:
            config = yaml.safe_load(fh)
        if 'drive' in config:
            DRIVE_SOURCE_PATH = config['drive']['source_path']
            DRIVE_TARGET_UUID = config['drive']['target_uuid']
        if 'emby' in config:
            EMBY_SERVER = config['emby']['server']
            EMBY_USER_ID = config['emby']['user_id']
            EMBY_USER_NAME = config['emby']['user_name']
            EMBY_USER_PASS = config['emby']['user_pass']
            EMBY_PLAYLIST_ID = config['emby']['playlist_id']
        if 'mail' in config:
            MAIL_SMTP_PORT = config['mail']['smtp_port']
            MAIL_SMTP_SERVER = config['mail']['smtp_server']
            MAIL_SENDER = config['mail']['sender']
            MAIL_RECEIVER = config['mail']['receiver']
            MAIL_PASSWORD = config['mail']['password']

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('block')
    for device in iter(monitor.poll, None):
        if device.get('ACTION') == 'add' and device.get('ID_FS_UUID') == DRIVE_TARGET_UUID:
            mountpoint = mount_partition(device.device_node, DRIVE_TARGET_UUID)
            if mountpoint:
                sync_playlists(mountpoint + '/')
                unmount_partition(device.device_node, DRIVE_TARGET_UUID)
                email_notification()

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
