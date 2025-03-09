#!/usr/bin/env python3

# Allow execution from anywhere
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import re
import subprocess

from pathlib import Path

from devscripts.tomlparse import parse_toml
from devscripts.utils import read_file


def parse_args():
    parser = argparse.ArgumentParser(
        description='Install dependencies for yt-dlp',
        epilog='Example usage:\n  python -m devscripts.install_deps --all -e test  # Install all dependencies except test group\n  python -m devscripts.install_deps -i dev -i test  # Install development and test dependencies\n  python -m devscripts.install_deps --only-optional -i dev -i test  # Install only dev and test dependencies',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'input', nargs='?', metavar='TOMLFILE', default=Path(__file__).parent.parent / 'pyproject.toml',
        help='input file (default: %(default)s)')
    parser.add_argument(
        '-e', '--exclude', metavar='DEPENDENCY', action='append',
        help='exclude a dependency')
    parser.add_argument(
        '-i', '--include', metavar='GROUP', action='append',
        help='include an optional dependency group')
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-a', '--all', action='store_true',
        help='include all optional dependency groups')
    group.add_argument(
        '-o', '--only-optional', action='store_true',
        help='only install specified optional dependencies (excludes core dependencies and default group)')
    parser.add_argument(
        '-p', '--print', action='store_true',
        help='only print requirements to stdout')
    parser.add_argument(
        '-u', '--user', action='store_true',
        help='install with pip as --user')
    return parser.parse_args()


def main():
    args = parse_args()
    project_table = parse_toml(read_file(args.input))['project']
    recursive_pattern = re.compile(rf'{project_table["name"]}\[(?P<group_name>[\w-]+)\]')
    optional_groups = project_table['optional-dependencies']
    excludes = args.exclude or []

    def yield_deps(group):
        for dep in group:
            if mobj := recursive_pattern.fullmatch(dep):
                yield from optional_groups.get(mobj.group('group_name'), [])
            else:
                yield dep

    targets = []
    if not args.only_optional:  # `-o` should exclude 'dependencies' and the 'default' group
        targets.extend(project_table['dependencies'])
        if 'default' not in excludes:  # `--exclude default` should exclude entire 'default' group
            targets.extend(yield_deps(optional_groups['default']))

    # If --all is specified, include all optional dependency groups
    if args.all:
        for group_name, group in optional_groups.items():
            if group_name != 'default' and group_name not in excludes:
                targets.extend(yield_deps(group))
    else:
        # Check if --only-optional is used without --include flags
        if args.only_optional and not args.include:
            import sys
            print('Warning: --only-optional has no effect without specifying groups with --include',
                  '         Use --all instead to include all optional dependency groups.',
                  file=sys.stderr, sep='\n')

        for include in filter(None, map(optional_groups.get, args.include or [])):
            targets.extend(yield_deps(include))

    # Remove duplicates and excluded dependencies
    seen = set()
    unique_targets = []
    for t in targets:
        base_name = re.match(r'[\w-]+', t).group(0).lower()
        if base_name not in excludes and t not in seen:
            seen.add(t)
            unique_targets.append(t)
    targets = unique_targets

    if args.print:
        for target in targets:
            print(target)
        return

    pip_args = [sys.executable, '-m', 'pip', 'install', '-U']
    if args.user:
        pip_args.append('--user')
    pip_args.extend(targets)

    return subprocess.call(pip_args)


if __name__ == '__main__':
    sys.exit(main())
