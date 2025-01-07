#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This program serves as a packager to create a snapshot of the current
pyLabSpec package. It is meant to run as a standalone program called
directly from the commandline, and accepts a number of input arguments
to control the packaging process. By default, it should create an
output file in the directory containing the pyLabSpec folder, ignoring
all the git-related files, as well as all user-generated files (*.pyc
and documentation files).

It's basically a front-end for git-archive, which is already well-
optimized for the task. Git will check the manifest according to what's
not ignored by any existing .gitignore files, and it will also check
the file .../pyLabSpec/Scripts/.gitattributes, which contains additional
instructions for including/excluding specific user-/experiment-specific
files.

Note that this deprecated and has been superceded simply by setuptools,
the python packager.. "python setup.py sdist" would yield the same result.
The file manifest has been updated to be up-to-date with the pyinstaller-
related packaging scripts for Windows.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import subprocess
import argparse
import datetime
# third-party
pass
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import miscfunctions

if sys.version_info[0] == 3:
	from importlib import reload
	xrange = range
	unicode = str




debugging = False
PACKAGEDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
## main command
def run_git_archive(output=None, tree=None, prefix=None, extra=None, check=False):
	cmd = ["git", "-C", PACKAGEDIR, "archive"]
	cmd += ["-o", output]
	if prefix is not None:
		cmd += ["--prefix=%s" % prefix]
	if extra is not None:
		cmd += extra
	cmd += [tree]
	
	if debugging:
		print("\nrunning the following command:\n>%s" % (" ".join(cmd)))
	
	if check:
		print("\nwould have run the following command:\n>%s" % (" ".join(cmd)))
		return True
	else:
		shellcommand = " ".join(cmd)
		result = subprocess.Popen(shellcommand, shell=True, stdout=subprocess.PIPE).communicate()[0]
		print("wrote output file to %s" % output)
		return result




if __name__ == '__main__':
	
	# define arguments
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"-d", "--debug", action='store_true',
		help="whether to add extra print messages to the terminal")
	parser.add_argument(
		"-c", "--check", action='store_true',
		help="whether to only check the final command, without running it")
	parser.add_argument("file", type=str, nargs='?',
		help="specify the exact output file (including path), otherwise it's built from individual options below")
	parser.add_argument("-o", "--output", default="pyLabSpec.tar",
		type=str, help="specify output filename (default: pyLabSpec.tar)")
	parser.add_argument("--directory", default="cwd",
		type=str, help="specify the output directory (default: cwd) (see --directory help for details)")
	parser.add_argument("--tree", default="HEAD", type=str, help="specify the tree-ish commmit/branch/tag")
	parser.add_argument("--prefix", default="pyLabSpec", type=str, help="prepends PREFIX/ to the archive contents (default: pyLabSpec)")
	parser.add_argument("--suffix", default=None,
		type=str, help="appends SUFFIX to the archive filename (see --suffix help for details)")
	parser.add_argument("--extra", default=None, nargs='+',
		type=str, help="specify extra options to send to the archiver backend")
	
	# parse arguments
	args = parser.parse_args()
	# check for command-specific help requests!
	debugging = args.debug
	if debugging:
		print("sys.argv is: ", sys.argv)
		print("CLI args were: ", args)
	if args.prefix is not None:
		if not args.prefix[-1] == "/":
			args.prefix += "/"
	if args.suffix == "None":
		args.suffix = None
	elif args.suffix == "help":
		print("Besides the general help information:\n")
		parser.print_help()
		print("\n-------------------------------------\n")
		print("One may also use specifiers to append special suffixes to the output filename:")
		print("\t%tree - the current tree/tag/branch (see note about --tree above)")
		print("\t%hash - the hash of the current commit (note: will not be accurate if tree is not HEAD!)")
		print("\t%ctime - the full date/time using the ctime method/format")
		print("\t%x - locale's date representation")
		print("\t%X - locale's time representation")
		print("\t%Y - year")
		print("\t%y - year, minus the century")
		print("\t%B - full month name")
		print("\t%b - abbreviated month name")
		print("\t%m - month")
		print("\t%-m - abbreviated month")
		print("\t%U - week of the year (Sunday as the first day of the week)")
		print("\t%W - week of the year (Monday as the first day of the week)")
		print("\t%j - day of the year")
		print("\t%d - zero-padded day of the month")
		print("\t%-d - day of the month")
		print("\t%A - weekday")
		print("\t%a - abbreviated weekday")
		print("\t%H - zero-padded hour (24-hour format)")
		print("\t%-H - hour (24-hour format)")
		print("\t%I - zero-padded hour (12-hour format)")
		print("\t%-I - hour (12-hour format)")
		print("\t%M - zero-padded minute")
		print("\t%-M - minute")
		print("\t%S - zero-padded second")
		print("\t%-S - second")
		print("\t%p - AM or PM")
		print("\nfor example, using '--suffix _%tree_%Y-%m-%d_%X' would append something like '_HEAD_2019-03-18_15:33:11'")
		sys.exit()
	elif args.suffix is not None:
		# replace special tags
		if "%tree" in args.suffix:
			args.suffix = args.suffix.replace("%tree", args.tree)
		if "%hash" in args.suffix:
			args.suffix = args.suffix.replace("%hash", miscfunctions.get_git_hash())
		today = datetime.datetime.now()
		if "%ctime" in args.suffix:
			args.suffix = args.suffix.replace("%ctime", today.ctime())
		hyphstrftimeletters = ["m", "d", "H", "I", "M", "S"]
		for letter in hyphstrftimeletters:
			strftimestring = "%-{}".format(letter)
			if strftimestring in args.suffix:
				args.suffix = args.suffix.replace(strftimestring, today.strftime(strftimestring))
		strftimeletters = ["x","X", "Y","y", "B","b","m", "U","W", "j","d","A","a", "H","I","M","S","p"]
		for letter in strftimeletters:
			strftimestring = "%{}".format(letter)
			if strftimestring in args.suffix:
				args.suffix = args.suffix.replace(strftimestring, today.strftime(strftimestring))
		# fix forbidden characters..
		args.suffix = args.suffix.replace("/", "-") # from dates
		# determine filename
		splitext = [None, None]
		if args.output[-4:] == ".zip":
			splitext = [args.output[:-4], ".zip"]
		elif args.output[-4:] == ".tar":
			splitext = [args.output[:-4], ".tar"]
		elif args.output[-7:] == ".tar.gz":
			splitext = [args.output[:-7], ".tar.gz"]
		args.output = "%s%s" % (splitext[0]+args.suffix, splitext[1])
	if args.directory == "help":
		print("Besides the general help information:\n")
		parser.print_help()
		print("\n-------------------------------------\n")
		print("One may also use specifiers to define a special directory locations, assuming that this")
		print("script sits in the directory ..../<PARENTDIR>/<PACKAGEDIR>/<MODULEDIR>/Scripts/archive_the_package.py:")
		print("\tcwd - the current working directory")
		print("\tparent - the parent directory of pyLabSpec (e.g., ....<PARENTDIR>/outputfile.tar)")
		print("\troot - the root directory within pyLabSpec (e.g., ..../<PACKAGEDIR>/outputfile.tar)")
		sys.exit()
	if args.file is None:
		directory = args.directory
		filename = args.output
		if directory == "cwd":
			directory = os.path.realpath(os.getcwd())
		elif directory == "parent":
			directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
		elif directory == "root":
			directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
		args.file = "'%s'" % (os.path.join(directory, filename))
	
	run_git_archive(
		output=args.file,
		tree=args.tree,
		prefix=args.prefix,
		extra=args.extra,
		check=args.check)
