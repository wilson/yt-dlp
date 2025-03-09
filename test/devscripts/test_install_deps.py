#!/usr/bin/env python3

import os
import sys
import unittest
from unittest import mock
from io import StringIO
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from devscripts import install_deps


class TestInstallDeps(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        # Helper method to create project data with configurable dependencies
        def create_project_data(
            dependencies=None,
            optional_deps=None,
        ):
            """
            Create a project data dictionary with customizable dependencies.

            Args:
                dependencies: List of core dependencies (defaults to ['dep1', 'dep2'])
                optional_deps: Dictionary of optional dependency groups
                              (defaults to standard set of default, test, and dev groups)

            Returns:
                Dictionary with project data structure
            """
            if dependencies is None:
                dependencies = ['dep1', 'dep2']

            if optional_deps is None:
                optional_deps = {
                    'default': ['opt1', 'opt2'],
                    'test': ['test1', 'test2'],
                    'dev': ['dev1', 'dev2'],
                }

            return {
                'project': {
                    'name': 'yt-dlp',
                    'dependencies': dependencies,
                    'optional-dependencies': optional_deps,
                },
            }

        # Common project data with standard dependencies
        self.standard_project_data = create_project_data()

        # Extended project data with an extra group
        self.extended_project_data = create_project_data(
            optional_deps={
                'default': ['opt1', 'opt2'],
                'test': ['test1', 'test2'],
                'dev': ['dev1', 'dev2'],
                'extra': ['extra1', 'extra2'],
            },
        )

        # Project data with recursive dependencies
        self.recursive_project_data = create_project_data(
            dependencies=['dep1'],
            optional_deps={
                'default': ['opt1'],
                'test': ['test1', 'yt-dlp[dev]'],  # test depends on dev
                'dev': ['dev1', 'dev2'],
            },
        )

        # Simple project data for custom input file test
        self.custom_input_project_data = create_project_data(
            dependencies=['dep1'],
            optional_deps={
                'default': ['opt1'],
            },
        )

        # Simplified project data for testing specific dependency exclusion
        self.simplified_project_data = create_project_data(
            optional_deps={
                'default': ['opt1', 'opt2'],
            },
        )

        # Project data for testing default group exclusion
        self.exclude_default_project_data = create_project_data(
            optional_deps={
                'default': ['opt1', 'opt2'],
                'test': ['test1', 'test2'],
            },
        )

        # Project data for testing multiple excludes
        self.multiple_excludes_project_data = create_project_data(
            dependencies=['dep1', 'dep2', 'dep3'],
            optional_deps={
                'default': ['opt1', 'opt2'],
                'test': ['test1', 'test2'],
                'dev': ['dev1', 'dev2'],
            },
        )

    @contextmanager
    def capture_output(self):
        """Capture stdout and stderr to StringIO objects"""
        new_out, new_err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield new_out, new_err
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def run_with_argv_and_capture(self, argv, mock_parse_toml=None, project_data=None, mock_call=None):
        """
        Run install_deps.main with given argv and return the captured output.

        Args:
            argv: List of command line arguments
            mock_parse_toml: Mock object for parse_toml (if provided)
            project_data: Project data to mock (if provided)
            mock_call: Mock object for subprocess.call to check if not called with --print flag

        Returns:
            Tuple of (printed_deps, error_output) where:
                printed_deps: List of dependencies printed to stdout
                error_output: String of error messages printed to stderr
        """
        if project_data and mock_parse_toml:
            mock_parse_toml.return_value = project_data

        with mock.patch('sys.argv', argv):
            with self.capture_output() as (output, error):
                install_deps.main()

                # Handle the output
                output_text = output.getvalue().strip()
                error_text = error.getvalue().strip()

                # Convert output to list of dependencies if not empty
                if output_text:
                    printed_deps = output_text.split('\n')
                else:
                    printed_deps = []

                # If --print is in argv and mock_call is provided, assert it wasn't called
                if mock_call and '--print' in argv:
                    mock_call.assert_not_called()

                return printed_deps, error_text

    def assert_deps_included(self, deps, expected_deps, msg=None):
        """
        Assert that all expected dependencies are included in the deps list.

        Args:
            deps: List of dependencies to check
            expected_deps: List of dependencies expected to be present
            msg: Optional message to display if assertion fails
        """
        for dep in expected_deps:
            self.assertIn(dep, deps, msg or f"Dependency '{dep}' should be included")

    def assert_deps_excluded(self, deps, excluded_deps, msg=None):
        """
        Assert that all excluded dependencies are not present in the deps list.

        Args:
            deps: List of dependencies to check
            excluded_deps: List of dependencies expected to be absent
            msg: Optional message to display if assertion fails
        """
        for dep in excluded_deps:
            self.assertNotIn(dep, deps, msg or f"Dependency '{dep}' should be excluded")

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_all_flag(self, mock_call, mock_read_file, mock_parse_toml):
        """Test the --all flag includes all dependencies."""
        mock_parse_toml.return_value = self.extended_project_data

        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--all', '--print'],
            mock_parse_toml,
            self.extended_project_data,
            mock_call,
        )

        # Check that all dependencies are included:
        # 2 from dependencies + all optional dependencies (2+2+2+2)
        self.assertEqual(len(printed_deps), 10)

        # Check core dependencies
        core_deps = ['dep1', 'dep2']
        self.assert_deps_included(printed_deps, core_deps)

        # Check all optional dependency groups
        default_deps = ['opt1', 'opt2']
        test_deps = ['test1', 'test2']
        dev_deps = ['dev1', 'dev2']
        extra_deps = ['extra1', 'extra2']

        self.assert_deps_included(printed_deps, default_deps)
        self.assert_deps_included(printed_deps, test_deps)
        self.assert_deps_included(printed_deps, dev_deps)
        self.assert_deps_included(printed_deps, extra_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_all_flag_with_exclude(self, mock_call, mock_read_file, mock_parse_toml):
        """Test the --all flag with --exclude excludes specified dependencies."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--all', '--exclude', 'test', '--print'],
            mock_parse_toml,
            self.standard_project_data,
            mock_call,
        )

        # Check that all dependencies except the excluded group are included
        self.assertEqual(len(printed_deps), 6)

        # Check core dependencies and included dependency groups
        included_deps = ['dep1', 'dep2', 'opt1', 'opt2', 'dev1', 'dev2']
        self.assert_deps_included(printed_deps, included_deps)

        # Check excluded dependency group
        excluded_deps = ['test1', 'test2']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    def test_mutually_exclusive_flags(self):
        """Test that --all and --only-optional are mutually exclusive."""
        # Capture stderr to suppress argparse error messages
        with self.capture_output() as (_, _):
            with self.assertRaises(SystemExit):
                with mock.patch('sys.argv', ['install_deps.py', '--all', '--only-optional']):
                    install_deps.parse_args()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_only_optional_warning(self, mock_call, mock_read_file, mock_parse_toml):
        """Test warning is issued when --only-optional is used without --include."""
        _, error_output = self.run_with_argv_and_capture(
            ['install_deps.py', '--only-optional', '--print'],
            mock_parse_toml,
            self.standard_project_data,
            mock_call,
        )

        # Check that a warning was printed to stderr
        self.assertIn('Warning: --only-optional has no effect without specifying groups', error_output)
        self.assertIn('Use --all instead', error_output)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_only_optional_with_include(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --only-optional with --include only includes specified group."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--only-optional', '--include', 'test', '--print'],
            mock_parse_toml,
            self.standard_project_data,
            mock_call,
        )

        # Specified optional group should be included
        included_deps = ['test1', 'test2']
        self.assert_deps_included(printed_deps, included_deps)

        # Core dependencies, default group, and non-specified optional group should be excluded
        excluded_deps = ['dep1', 'dep2', 'opt1', 'opt2', 'dev1', 'dev2']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_multiple_includes(self, mock_call, mock_read_file, mock_parse_toml):
        """Test multiple --include flags include all specified groups."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--include', 'test', '--include', 'dev', '--print'],
            mock_parse_toml,
            self.standard_project_data,
            mock_call,
        )

        # Should include core dependencies, default group, and both specified groups
        self.assertEqual(len(printed_deps), 8)

        # All dependencies should be included (core, default, test, dev)
        all_deps = ['dep1', 'dep2', 'opt1', 'opt2', 'test1', 'test2', 'dev1', 'dev2']
        self.assert_deps_included(printed_deps, all_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_exclude_default_group(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --exclude default excludes the default group."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'default', '--print'],
            mock_parse_toml,
            self.exclude_default_project_data,
            mock_call,
        )

        # Should include only core dependencies
        self.assertEqual(len(printed_deps), 2)

        # Core dependencies should be included
        included_deps = ['dep1', 'dep2']
        self.assert_deps_included(printed_deps, included_deps)

        # Default group should be excluded
        excluded_deps = ['opt1', 'opt2']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_exclude_specific_dependency(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --exclude for a specific dependency excludes only that dependency."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'dep1', '--print'],
            mock_parse_toml,
            self.simplified_project_data,
            mock_call,
        )

        # Should have 3 dependencies (dep2, opt1, opt2)
        self.assertEqual(len(printed_deps), 3)

        # Other dependencies should be included
        included_deps = ['dep2', 'opt1', 'opt2']
        self.assert_deps_included(printed_deps, included_deps)

        # dep1 should be excluded
        excluded_deps = ['dep1']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_multiple_excludes(self, mock_call, mock_read_file, mock_parse_toml):
        """Test multiple --exclude flags exclude all specified dependencies/groups."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'dep1', '--exclude', 'test', '--exclude', 'dev', '--print'],
            mock_parse_toml,
            self.multiple_excludes_project_data,
            mock_call,
        )

        # Should include core dependencies (minus dep1) and default group
        self.assertEqual(len(printed_deps), 4)

        # Remaining dependencies should be included
        included_deps = ['dep2', 'dep3', 'opt1', 'opt2']
        self.assert_deps_included(printed_deps, included_deps)

        # Excluded dependency and groups should be excluded
        excluded_deps = ['dep1', 'test1', 'test2', 'dev1', 'dev2']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_recursive_dependencies(self, mock_call, mock_read_file, mock_parse_toml):
        """Test recursive dependencies are properly resolved."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--include', 'test', '--print'],
            mock_parse_toml,
            self.recursive_project_data,
            mock_call,
        )

        # Should include core, default, test, and dev (recursively)
        self.assertEqual(len(printed_deps), 5)

        # All dependencies should be included
        all_deps = ['dep1', 'opt1', 'test1', 'dev1', 'dev2']
        self.assert_deps_included(printed_deps, all_deps)

        # The reference itself should be resolved and not included
        excluded_deps = ['yt-dlp[dev]']
        self.assert_deps_excluded(printed_deps, excluded_deps)

    def test_user_flag(self):
        """Test the --user flag is properly recognized."""
        with mock.patch('sys.argv', ['install_deps.py', '--user']):
            args = install_deps.parse_args()
            self.assertTrue(args.user, 'The --user flag should be True')

        with mock.patch('sys.argv', ['install_deps.py']):
            args = install_deps.parse_args()
            self.assertFalse(args.user, 'The --user flag should be False by default')

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_custom_input_file(self, mock_call, mock_read_file, mock_parse_toml):
        """Test specifying a custom input file."""
        custom_path = '/custom/path/pyproject.toml'

        # Use the run_with_argv_and_capture helper with custom arguments
        _, _ = self.run_with_argv_and_capture(
            ['install_deps.py', custom_path, '--print'],
            mock_parse_toml,
            self.custom_input_project_data,
            mock_call,
        )

        # Check that read_file was called with the custom path
        mock_read_file.assert_called_once_with(custom_path)


if __name__ == '__main__':
    unittest.main()
