#!/usr/bin/python

import os
import datetime
from shutil import copy2
import sys
from subprocess import call, Popen, PIPE
import json

config_file = os.path.join(os.path.dirname(__file__), "config.json")
sources = json.load(open(config_file, "rt"))["sources"]

# read cmd line
if len(sys.argv) > 1:
    sources = [s for s in sources if s[0] in sys.argv[1:]]

destination = '/backup/weekly' if "-W" in sys.argv[1:] else '/backup'
destination_dropbox = '/home/francois/Dropbox/saves'
destination_hubic = '/backup/hubic'
cwd = "/home/francois/scripts"
key_file = "/backup/crypt_key"

rsync_options = ['--recursive',
                 '--archive',
                 '--delete',
                 '--delete-excluded',
                 '--compress',
                 '--stats',
                 '--progress',
                 #  '--itemize-changes',
                 '--prune-empty-dirs']
if "-d" in sys.argv[1:]:
    rsync_options.append('--dry-run')


def run_print_and_save_output(cmdline):
    output = ""
    p = Popen(cmdline + " 2>&1", stdout=PIPE, bufsize=1, shell=True)
    for line in iter(p.stdout.readline, b''):
        print line,
        output += line
    p.stdout.close()
    p.wait()
    return output, p.returncode


def run_rsync(cmd_list, source, destination, bwlimit=0, timestamp=False):
    error = ""
    if timestamp:
        with open(os.path.join(source, "timestamp"), "wt") as timestamp_f:
            timestamp_f.write(str(datetime.datetime.now()))
    string_cmd = " ".join(cmd_list + ["--bwlimit=%d" % bwlimit, source, destination])
    print "Running Rsync command: " + string_cmd
    ret_str, rc = run_print_and_save_output(string_cmd)
    print "rsync error code", rc
    if rc != 0 and rc != 23:
        sys.exit(1)
    found_line = False
    some_files_were_added = False
    for line in ret_str.splitlines():
        if "Number of regular files trans" in line:
            some_files_were_added = ": 0" not in line
            found_line = True
            break
    if not found_line:
        # default to true but mark as error
        some_files_were_added = True
        error += "error didn't find number of files trans! in %s\n" % s[0]
    print "some_files_were_added", some_files_were_added
    return some_files_were_added

cmd = ["rsync"] + rsync_options
error = ""
for i, s in enumerate(sources):
    filters = "rsync_filters" if not "-light" in s[2:] else "rsync_filters_light"
    final_cmd = list(cmd)
    final_cmd.append('--filter=\'merge /home/francois/scripts/' + filters + '\'')
    final_cmd += [a for a in s if a.startswith("--")]
    source = "'" + s[1].replace(' ', '\\ ') + "'"
    local_destination = os.path.join(destination, s[0])
    print "Backup " + s[0] + " (" + str(i + 1) + "/" + str(len(sources)) + ")"
    some_files_were_added = False
    srcs = [source]
    dsts = [local_destination]
    timestamps = [False]  # first rsync does not need to create timestamp file
    if "-ks1" in s[2:]:
        # copy from local
        srcs += [local_destination]
        dsts += ["ks1:backup/backup"]
        timestamps.append(True)
    for src, dst, timestamp in zip(srcs, dsts, timestamps):
        # bwlimit is internet upload (":" in destination)
        bwlimit = 60 if ":" in dst else 0
        added_this_time = run_rsync(final_cmd, src, dst, bwlimit, timestamp)
        some_files_were_added = some_files_were_added or added_this_time
    # check for archiving
    dropbox = "-dropbox" in s[2:]
    hubic = "-hubic" in s[2:]
    needs_tgz = dropbox or hubic
    print "needs_tgz", needs_tgz, dropbox, hubic
    if needs_tgz and some_files_were_added:
        # want dropbox, need to tgz
        tar_cmd = "tar -cvzf " + s[0] + ".tgz " + local_destination
        print tar_cmd
        print destination
        ret = call(tar_cmd, shell=True, cwd=destination)
        if ret != 0:
            print "tar error code", ret
            sys.exit(1)
        else:
            print "Tar Done Successfully"
        # crypt the file
        crypt_cmd = "ccencrypt -f -k " + key_file + " " + local_destination + ".tgz"
        print crypt_cmd
        ret = call(crypt_cmd, shell=True)
        if ret != 0:
            print "ccencrypt error code", ret
            sys.exit(1)
        else:
            print "ccencrypt successfull"

        if dropbox:
            # copy file to dropbox
            copy2(local_destination + ".tgz.cpt", destination_dropbox)
            print "file copied to dropbox"
        if hubic:
            # copy file to hubic
            copy2(local_destination + ".tgz.cpt", destination_hubic)
            print "file copied to hubic"

if len(error) > 0:
    print error
    sys.exit(1)

