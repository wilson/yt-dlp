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
        """Set up test fixtures, if any."""
        # Common project data with standard dependencies
        self.standard_project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1', 'dep2'],
                'optional-dependencies': {
                    'default': ['opt1', 'opt2'],
                    'test': ['test1', 'test2'],
                    'dev': ['dev1', 'dev2'],
                },
            },
        }

        # Extended project data with an extra group
        self.extended_project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1', 'dep2'],
                'optional-dependencies': {
                    'default': ['opt1', 'opt2'],
                    'test': ['test1', 'test2'],
                    'dev': ['dev1', 'dev2'],
                    'extra': ['extra1', 'extra2'],
                },
            },
        }

        # Project data with recursive dependencies
        self.recursive_project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1'],
                'optional-dependencies': {
                    'default': ['opt1'],
                    'test': ['test1', 'yt-dlp[dev]'],  # test depends on dev
                    'dev': ['dev1', 'dev2'],
                },
            },
        }

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

    def run_with_argv_and_capture(self, argv, mock_parse_toml=None, project_data=None):
        """
        Run install_deps.main with given argv and return the captured output.

        Args:
            argv: List of command line arguments
            mock_parse_toml: Mock object for parse_toml (if provided)
            project_data: Project data to mock (if provided)

        Returns:
            Tuple of (printed_deps, error_output, mock_call)
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

                return printed_deps, error_text

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
        )

        # Check that all dependencies are included:
        # 2 from dependencies + all optional dependencies (2+2+2+2)
        self.assertEqual(len(printed_deps), 10)

        # Check core dependencies
        self.assertIn('dep1', printed_deps)
        self.assertIn('dep2', printed_deps)

        # Check all optional dependency groups
        self.assertIn('opt1', printed_deps)
        self.assertIn('opt2', printed_deps)
        self.assertIn('test1', printed_deps)
        self.assertIn('test2', printed_deps)
        self.assertIn('dev1', printed_deps)
        self.assertIn('dev2', printed_deps)
        self.assertIn('extra1', printed_deps)
        self.assertIn('extra2', printed_deps)

        # Call was not made because we used --print
        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_all_flag_with_exclude(self, mock_call, mock_read_file, mock_parse_toml):
        """Test the --all flag with --exclude excludes specified dependencies."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--all', '--exclude', 'test', '--print'],
            mock_parse_toml,
            self.standard_project_data,
        )

        # Check that all dependencies except the excluded group are included
        self.assertEqual(len(printed_deps), 6)

        # Check core dependencies
        self.assertIn('dep1', printed_deps)
        self.assertIn('dep2', printed_deps)

        # Check included dependency groups
        self.assertIn('opt1', printed_deps)
        self.assertIn('opt2', printed_deps)
        self.assertIn('dev1', printed_deps)
        self.assertIn('dev2', printed_deps)

        # Check excluded dependency group
        self.assertNotIn('test1', printed_deps)
        self.assertNotIn('test2', printed_deps)

        # Call was not made because we used --print
        mock_call.assert_not_called()

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
        )

        # Check that a warning was printed to stderr
        self.assertIn('Warning: --only-optional has no effect without specifying groups', error_output)
        self.assertIn('Use --all instead', error_output)

        # Call was not made because we used --print
        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_only_optional_with_include(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --only-optional with --include only includes specified group."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--only-optional', '--include', 'test', '--print'],
            mock_parse_toml,
            self.standard_project_data,
        )

        # Check that only the specified optional dependencies are included
        # Core dependencies should be excluded
        self.assertNotIn('dep1', printed_deps)
        self.assertNotIn('dep2', printed_deps)

        # Default group should be excluded
        self.assertNotIn('opt1', printed_deps)
        self.assertNotIn('opt2', printed_deps)

        # Specified optional group should be included
        self.assertIn('test1', printed_deps)
        self.assertIn('test2', printed_deps)

        # Non-specified optional group should be excluded
        self.assertNotIn('dev1', printed_deps)
        self.assertNotIn('dev2', printed_deps)

        # Call was not made because we used --print
        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_multiple_includes(self, mock_call, mock_read_file, mock_parse_toml):
        """Test multiple --include flags include all specified groups."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--include', 'test', '--include', 'dev', '--print'],
            mock_parse_toml,
            self.standard_project_data,
        )

        # Should include core dependencies, default group, and both specified groups
        self.assertEqual(len(printed_deps), 8)

        # Core dependencies and default group
        self.assertIn('dep1', printed_deps)
        self.assertIn('dep2', printed_deps)
        self.assertIn('opt1', printed_deps)
        self.assertIn('opt2', printed_deps)

        # Both included groups
        self.assertIn('test1', printed_deps)
        self.assertIn('test2', printed_deps)
        self.assertIn('dev1', printed_deps)
        self.assertIn('dev2', printed_deps)

        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_exclude_default_group(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --exclude default excludes the default group."""
        # Modify project data to suit this test
        project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1', 'dep2'],
                'optional-dependencies': {
                    'default': ['opt1', 'opt2'],
                    'test': ['test1', 'test2'],
                },
            },
        }

        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'default', '--print'],
            mock_parse_toml,
            project_data,
        )

        # Should include only core dependencies
        self.assertEqual(len(printed_deps), 2)

        # Core dependencies
        self.assertIn('dep1', printed_deps)
        self.assertIn('dep2', printed_deps)

        # Default group should be excluded
        self.assertNotIn('opt1', printed_deps)
        self.assertNotIn('opt2', printed_deps)

        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_exclude_specific_dependency(self, mock_call, mock_read_file, mock_parse_toml):
        """Test --exclude for a specific dependency excludes only that dependency."""
        # Simplify project data for this test
        project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1', 'dep2'],
                'optional-dependencies': {
                    'default': ['opt1', 'opt2'],
                },
            },
        }

        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'dep1', '--print'],
            mock_parse_toml,
            project_data,
        )

        # Should have 3 dependencies (dep2, opt1, opt2)
        self.assertEqual(len(printed_deps), 3)

        # dep1 should be excluded
        self.assertNotIn('dep1', printed_deps)

        # Other dependencies should be included
        self.assertIn('dep2', printed_deps)
        self.assertIn('opt1', printed_deps)
        self.assertIn('opt2', printed_deps)

        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_multiple_excludes(self, mock_call, mock_read_file, mock_parse_toml):
        """Test multiple --exclude flags exclude all specified dependencies/groups."""
        # Add an extra core dependency for this test
        project_data = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1', 'dep2', 'dep3'],
                'optional-dependencies': {
                    'default': ['opt1', 'opt2'],
                    'test': ['test1', 'test2'],
                    'dev': ['dev1', 'dev2'],
                },
            },
        }

        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--exclude', 'dep1', '--exclude', 'test', '--exclude', 'dev', '--print'],
            mock_parse_toml,
            project_data,
        )

        # Should include core dependencies (minus dep1) and default group
        self.assertEqual(len(printed_deps), 4)

        # Check excluded dependency
        self.assertNotIn('dep1', printed_deps)

        # Other core dependencies should be included
        self.assertIn('dep2', printed_deps)
        self.assertIn('dep3', printed_deps)

        # Default group should be included
        self.assertIn('opt1', printed_deps)
        self.assertIn('opt2', printed_deps)

        # Excluded groups should be excluded
        self.assertNotIn('test1', printed_deps)
        self.assertNotIn('test2', printed_deps)
        self.assertNotIn('dev1', printed_deps)
        self.assertNotIn('dev2', printed_deps)

        mock_call.assert_not_called()

    @mock.patch('devscripts.install_deps.parse_toml')
    @mock.patch('devscripts.install_deps.read_file')
    @mock.patch('devscripts.install_deps.subprocess.call')
    def test_recursive_dependencies(self, mock_call, mock_read_file, mock_parse_toml):
        """Test recursive dependencies are properly resolved."""
        printed_deps, _ = self.run_with_argv_and_capture(
            ['install_deps.py', '--include', 'test', '--print'],
            mock_parse_toml,
            self.recursive_project_data,
        )

        # Should include core, default, test, and dev (recursively)
        self.assertEqual(len(printed_deps), 5)

        # All dependencies should be included
        self.assertIn('dep1', printed_deps)
        self.assertIn('opt1', printed_deps)
        self.assertIn('test1', printed_deps)
        self.assertIn('dev1', printed_deps)
        self.assertIn('dev2', printed_deps)

        # The reference itself should be resolved and not included
        self.assertNotIn('yt-dlp[dev]', printed_deps)

        mock_call.assert_not_called()

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
    def test_custom_input_file(self, mock_read_file, mock_parse_toml):
        """Test specifying a custom input file."""
        custom_path = '/custom/path/pyproject.toml'
        mock_parse_toml.return_value = {
            'project': {
                'name': 'yt-dlp',
                'dependencies': ['dep1'],
                'optional-dependencies': {
                    'default': ['opt1'],
                },
            },
        }

        # Test with custom input file and --print
        with mock.patch('sys.argv', ['install_deps.py', custom_path, '--print']):
            with self.capture_output() as (_, _):
                install_deps.main()

                # Check that read_file was called with the custom path
                mock_read_file.assert_called_once_with(custom_path)


if __name__ == '__main__':
    unittest.main()
