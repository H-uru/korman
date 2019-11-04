#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

import argparse
from pathlib import Path
from PyHSPlasma import *
import shutil
import subprocess
import sys
import time
import traceback

main_parser = argparse.ArgumentParser(description="Korman Plasma Launcher")
main_parser.add_argument("cwd", type=Path, help="Working directory of the client")
main_parser.add_argument("age", type=str, help="Name of the age to launch into")

sub_parsers = main_parser.add_subparsers(title="Plasma Version", dest="version",)
moul_parser = sub_parsers.add_parser("pvMoul")
moul_parser.add_argument("ki", type=int, help="KI Number of the desired player")
moul_parser.add_argument("--serverini", type=str, default="server.ini")
sp_parser = sub_parsers.add_parser("pvPots", aliases=["pvPrime"])
sp_parser.add_argument("player", type=str, help="Name of the desired player")

autolink_chron_name = "OfflineKIAutoLink"

if sys.platform == "win32":
    client_executables = {
        "pvMoul": "plClient.exe",
        "pvPots": "UruExplorer.exe"
    }
else:
    client_executables = {
        "pvMoul": "plClient",
        "pvPots": "UruExplorer"
    }

def die(*args, **kwargs):
    assert args
    if len(args) == 1 and not kwargs:
        sys.stderr.write(args[0])
    else:
        sys.stderr.write(args[0].format(*args[1:], **kwargs))
    sys.stdout.write("DIE\n")
    sys.exit(1)

def write(*args, **kwargs):
    assert args
    if len(args) == 1 and not kwargs:
        sys.stdout.write(args[0])
    else:
        sys.stdout.write(args[0].format(*args[1:], **kwargs))
    sys.stdout.write("\n")
    # And this is why we aren't using print()...
    sys.stdout.flush()

def backup_vault_dat(path):
    backup_path = path.with_suffix(".dat.korman_backup")
    shutil.copy2(str(path), str(backup_path))
    write("DBG: Copied vault backup: {}", backup_path)

def set_link_chronicle(store, new_value, cond_value=None):
    chron_folder = next((i for i in store.getChildren(store.firstNodeID)
                           if getattr(i, "folderType", None) == plVault.kChronicleFolder), None)
    if chron_folder is None:
        die("Could not locate vault chronicle folder.")
    autolink_chron = next((i for i in store.getChildren(chron_folder.nodeID)
                             if getattr(i, "entryName", None) == autolink_chron_name), None)
    if autolink_chron is None:
        write("DBG: Creating AutoLink chronicle...")
        autolink_chron = plVaultChronicleNode()
        autolink_chron.entryName = autolink_chron_name
        previous_value = ""
        store.addRef(chron_folder.nodeID, store.lastNodeID + 1)
    else:
        write("DBG: Found AutoLink chronicle...")
        previous_value = autolink_chron.entryValue

    # Have to submit the changed node to the store
    if cond_value is None or previous_value == cond_value:
        write("DBG: AutoLink = '{}' (previously: '{}')", new_value, previous_value)
        autolink_chron.entryValue = new_value
        store.addNode(autolink_chron)
    else:
        write("DBG: ***Not*** changing chronicle! AutoLink = '{}' (expected: '{}')", previous_value, cond_value)

    return previous_value

def find_player_vault(cwd, name):
    sav_dir = cwd.joinpath("sav")
    if not sav_dir.is_dir():
        die("Could not locate sav directory.")
    for i in sav_dir.iterdir():
        if not i.is_dir():
            continue
        current_dir = i.joinpath("current")
        if not current_dir.is_dir():
            continue
        vault_dat = current_dir.joinpath("vault.dat")
        if not vault_dat.is_file():
            continue

        store = plVaultStore()
        store.Import(str(vault_dat))

        # First node is the Player node...
        playerNode = store[store.firstNodeID]
        if playerNode.playerName == name:
            write("DBG: Vault found: {}", vault_dat)
            return vault_dat, store
    die("Could not locate the requested player vault.")

def main():
    print("DBG: alive")
    args = main_parser.parse_args()

    executable = args.cwd.joinpath(client_executables[args.version])
    if not executable.is_file():
        die("Failed to locate client executable.")

    # Have to find and mod the single player vault...
    if args.version == "pvPots":
        vault_path, vault_store = find_player_vault(args.cwd, args.player)
        backup_vault_dat(vault_path)
        vault_prev_autolink = set_link_chronicle(vault_store, args.age)
        write("DBG: Saving vault...")
        vault_store.Export(str(vault_path))

        # Update init file for this schtuff...
        init_path = args.cwd.joinpath("init", "net_age.fni")
        with plEncryptedStream().open(str(init_path), fmWrite, plEncryptedStream.kEncXtea) as ini:
            ini.writeLine("# This file was automatically generated by Korman.")
            ini.writeLine("Nav.PageInHoldList GlobalAnimations")
            ini.writeLine("Net.SetPlayer {}".format(vault_store.firstNodeID))
            ini.writeLine("Net.SetPlayerByName \"{}\"".format(args.player))
            # BUT WHY??? You ask...
            # Because, sayeth Hoikas, if this command is not executed, you will remain ensconsed
            # in the black void of the Link... forever... Sadly, it accepts no arguments and determines
            # whether to link to AvatarCustomization, Cleft, Demo (whee!), or Personal all by itself.
            ini.writeLine("Net.JoinDefaultAge")

        # When URU runs, the player may change the vault. Remove any temptation to play with
        # the stale vault...
        del vault_store

        # Sigh...
        time.sleep(1.0)

        # EXE args
        plasma_args = [str(executable), "-iinit", "To_Dni"]
    else:
        write("DBG: Using a superior client :) :) :)")
        plasma_args = [str(executable), "-LocalData", "-SkipLoginDialog", "-ServerIni={}".format(args.serverini),
                       "-PlayerId={}".format(args.ki), "-Age={}".format(args.age)]
    try:
        proc = subprocess.Popen(plasma_args, cwd=str(args.cwd), shell=True)

        # signal everything is a-ok -- causes blender to detach
        write("PLASMA_RUNNING")

        # Wait for things to finish
        proc.wait()
    finally:
        # Restore sp vault, if needed.
        if args.version == "pvPots":
            # Path of the Shell seems to have some sort of weird racing with the vault.dat around
            # shutdown. This delay helps somewhat in that regard.
            time.sleep(1.0)

            vault_store = plVaultStore()
            vault_store.Import(str(vault_path))
            new_prev_autolink = set_link_chronicle(vault_store, vault_prev_autolink, args.age)
            if new_prev_autolink != args.age:
                write("DBG: ***Not*** resaving the vault!")
            else:
                write("DBG: Resaving vault...")
                vault_store.Export(str(vault_path))

    # All good!
    write("DONE")
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if isinstance(e, SystemExit):
            raise
        else:
            die(traceback.format_exc())
