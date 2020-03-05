# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Test the functionality of the cifuzz module's functions:
1. Building fuzzers.
2. Running fuzzers.
"""
import json
import os
import pickle
import shutil
import sys
import tempfile
import unittest
import unittest.mock

# pylint: disable=wrong-import-position
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cifuzz
import fuzz_target

# NOTE: This integration test relies on
# https://github.com/google/oss-fuzz/tree/master/projects/example project.
EXAMPLE_PROJECT = 'example'

# Location of files used for testing.
TEST_FILES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'test_files')

# An example fuzzer that triggers an crash.
# Binary is a copy of the example project's do_stuff_fuzzer and can be
# generated by running "python3 infra/helper.py build_fuzzers example".
EXAMPLE_CRASH_FUZZER = 'example_crash_fuzzer'

# An example fuzzer that does not trigger a crash.
# Binary is a modified version of example project's do_stuff_fuzzer. It is
# created by removing the bug in my_api.cpp.
EXAMPLE_NOCRASH_FUZZER = 'example_nocrash_fuzzer'

# A fuzzer to be built in build_fuzzers integration tests.
EXAMPLE_BUILD_FUZZER = 'do_stuff_fuzzer'


class BuildFuzzersIntegrationTest(unittest.TestCase):
  """Test build_fuzzers function in the utils module."""

  def test_valid_commit(self):
    """Test building fuzzers with valid inputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(
              EXAMPLE_PROJECT,
              'oss-fuzz',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))
      self.assertTrue(
          os.path.exists(os.path.join(out_path, EXAMPLE_BUILD_FUZZER)))

  def test_valid_pull_request(self):
    """Test building fuzzers with valid pull request."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                               'oss-fuzz',
                               tmp_dir,
                               pr_ref='refs/pull/1757/merge'))
      self.assertTrue(
          os.path.exists(os.path.join(out_path, EXAMPLE_BUILD_FUZZER)))

  def test_invalid_pull_request(self):
    """Test building fuzzers with invalid pull request."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertFalse(
          cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                               'oss-fuzz',
                               tmp_dir,
                               pr_ref='ref-1/merge'))

  def test_invalid_project_name(self):
    """Test building fuzzers with invalid project name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertFalse(
          cifuzz.build_fuzzers(
              'not_a_valid_project',
              'oss-fuzz',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))

  def test_invalid_repo_name(self):
    """Test building fuzzers with invalid repo name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertFalse(
          cifuzz.build_fuzzers(
              EXAMPLE_PROJECT,
              'not-real-repo',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))

  def test_invalid_commit_sha(self):
    """Test building fuzzers with invalid commit SHA."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      with self.assertRaises(AssertionError):
        cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                             'oss-fuzz',
                             tmp_dir,
                             commit_sha='')

  def test_invalid_workspace(self):
    """Test building fuzzers with invalid workspace."""
    self.assertFalse(
        cifuzz.build_fuzzers(
            EXAMPLE_PROJECT,
            'oss-fuzz',
            'not/a/dir',
            commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523',
        ))


class RunFuzzersIntegrationTest(unittest.TestCase):
  """Test build_fuzzers function in the cifuzz module."""

  def tearDown(self):
    """Remove any existing crashes and test files."""
    out_dir = os.path.join(TEST_FILES_PATH, 'out')
    for out_file in os.listdir(out_dir):
      out_path = os.path.join(out_dir, out_file)
      #pylint: disable=consider-using-in
      if out_file == EXAMPLE_CRASH_FUZZER or out_file == EXAMPLE_NOCRASH_FUZZER:
        continue
      if os.path.isdir(out_path):
        shutil.rmtree(out_path)
      else:
        os.remove(out_path)

  def test_new_bug_found(self):
    """Test run_fuzzers with a valid build."""
    # Set the first return value to True, then the second to False to
    # emulate a bug existing in the current PR but not on the downloaded
    # OSS-Fuzz build.
    with unittest.mock.patch.object(fuzz_target.FuzzTarget,
                                    'is_reproducible',
                                    side_effect=[True, False]):
      run_success, bug_found = cifuzz.run_fuzzers(10, TEST_FILES_PATH,
                                                  EXAMPLE_PROJECT)
      build_dir = os.path.join(TEST_FILES_PATH, 'out', 'oss_fuzz_latest')
      self.assertTrue(os.path.exists(build_dir))
      self.assertNotEqual(0, len(os.listdir(build_dir)))
      self.assertTrue(run_success)
      self.assertTrue(bug_found)

  def test_old_bug_found(self):
    """Test run_fuzzers with a bug found in OSS-Fuzz before."""
    with unittest.mock.patch.object(fuzz_target.FuzzTarget,
                                    'is_reproducible',
                                    side_effect=[True, True]):
      run_success, bug_found = cifuzz.run_fuzzers(10, TEST_FILES_PATH,
                                                  EXAMPLE_PROJECT)
      build_dir = os.path.join(TEST_FILES_PATH, 'out', 'oss_fuzz_latest')
      self.assertTrue(os.path.exists(build_dir))
      self.assertNotEqual(0, len(os.listdir(build_dir)))
      self.assertTrue(run_success)
      self.assertFalse(bug_found)

  def test_invalid_build(self):
    """Test run_fuzzers with an invalid build."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      run_success, bug_found = cifuzz.run_fuzzers(10, tmp_dir, EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)

  def test_invalid_fuzz_seconds(self):
    """Tests run_fuzzers with an invalid fuzz seconds."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      run_success, bug_found = cifuzz.run_fuzzers(0, tmp_dir, EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)

  def test_invalid_out_dir(self):
    """Tests run_fuzzers with an invalid out directory."""
    run_success, bug_found = cifuzz.run_fuzzers(100, 'not/a/valid/path',
                                                EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)


class ParseOutputUnitTest(unittest.TestCase):
  """Test parse_fuzzer_output function in the cifuzz module."""

  def test_parse_valid_output(self):
    """Checks that the parse fuzzer output can correctly parse output."""
    test_output_path = os.path.join(TEST_FILES_PATH,
                                    'example_crash_fuzzer_output.txt')
    test_summary_path = os.path.join(TEST_FILES_PATH, 'bug_summary_example.txt')
    with tempfile.TemporaryDirectory() as tmp_dir:
      with open(test_output_path, 'r') as test_fuzz_output:
        cifuzz.parse_fuzzer_output(test_fuzz_output.read(), tmp_dir)
      result_files = ['bug_summary.txt']
      self.assertCountEqual(os.listdir(tmp_dir), result_files)

      # Compare the bug summaries.
      with open(os.path.join(tmp_dir, 'bug_summary.txt'), 'r') as bug_summary:
        detected_summary = bug_summary.read()
      with open(os.path.join(test_summary_path), 'r') as bug_summary:
        real_summary = bug_summary.read()
      self.assertEqual(detected_summary, real_summary)

  def test_parse_invalid_output(self):
    """Checks that no files are created when an invalid input was given."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      cifuzz.parse_fuzzer_output('not a valid output_string', tmp_dir)
      self.assertEqual(len(os.listdir(tmp_dir)), 0)


class CheckFuzzerBuildUnitTest(unittest.TestCase):
  """Tests the check_fuzzer_build function in the cifuzz module."""

  def test_correct_fuzzer_build(self):
    """Checks check_fuzzer_build function returns True for valid fuzzers."""
    test_fuzzer_dir = os.path.join(TEST_FILES_PATH, 'out')
    self.assertTrue(cifuzz.check_fuzzer_build(test_fuzzer_dir))

  def test_not_a_valid_fuzz_path(self):
    """Tests that False is returned when a bad path is given."""
    self.assertFalse(cifuzz.check_fuzzer_build('not/a/valid/path'))

  def test_not_a_valid_fuzzer(self):
    """Checks a directory that exists but does not have fuzzers is False."""
    self.assertFalse(cifuzz.check_fuzzer_build(TEST_FILES_PATH))


class GetFilesCoveredByTargetUnitTest(unittest.TestCase):
  """Test to get the files covered by a fuzz target in the cifuzz module."""

  example_cov_json = 'example_curl_cov.json'
  example_fuzzer_cov_json = 'example_curl_fuzzer_cov.json'
  example_fuzzer = 'curl_fuzzer'
  example_curl_file_list = 'example_curl_file_list'

  def setUp(self):
    with open(os.path.join(TEST_FILES_PATH, self.example_cov_json),
              'r') as file:
      self.proj_cov_report_example = json.loads(file.read())
    with open(os.path.join(TEST_FILES_PATH, self.example_fuzzer_cov_json),
              'r') as file:
      self.fuzzer_cov_report_example = json.loads(file.read())

  def test_valid_target(self):
    """Tests that covered files can be retrieved from a coverage report."""

    with unittest.mock.patch.object(
        cifuzz,
        'get_target_coverage_report',
        return_value=self.fuzzer_cov_report_example):
      file_list = cifuzz.get_files_covered_by_target(
          self.proj_cov_report_example, self.example_fuzzer, '/src/curl')

    with open(os.path.join(TEST_FILES_PATH, 'example_curl_file_list'),
              'rb') as file_handle:
      true_files_list = pickle.load(file_handle)
    self.assertCountEqual(file_list, true_files_list)

  def test_invalid_target(self):
    """Test asserts an invalid fuzzer returns None."""
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           'not-a-fuzzer', '/src/curl'))
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example, '',
                                           '/src/curl'))

  def test_invalid_project_build_dir(self):
    """Test asserts an invalid build dir returns None."""
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           self.example_fuzzer, '/no/pe'))
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           self.example_fuzzer, ''))


class GetTargetCoverageReporUnitTest(unittest.TestCase):
  """Test get_target_coverage_report function in the cifuzz module."""

  example_cov_json = 'example_curl_cov.json'
  example_fuzzer = 'curl_fuzzer'

  def setUp(self):
    with open(os.path.join(TEST_FILES_PATH, self.example_cov_json),
              'r') as file:
      self.cov_exmp = json.loads(file.read())

  def test_valid_target(self):
    """Test a target's coverage report can be downloaded and parsed."""
    with unittest.mock.patch.object(cifuzz,
                                    'get_json_from_url',
                                    return_value='{}') as mock_get_json:
      cifuzz.get_target_coverage_report(self.cov_exmp, self.example_fuzzer)
      (url,), _ = mock_get_json.call_args
      self.assertEqual(
          'https://storage.googleapis.com/oss-fuzz-coverage/'
          'curl/fuzzer_stats/20200226/curl_fuzzer.json', url)

  def test_invalid_target(self):
    """Test an invalid target coverage report will be None."""
    self.assertIsNone(
        cifuzz.get_target_coverage_report(self.cov_exmp, 'not-valid-target'))
    self.assertIsNone(cifuzz.get_target_coverage_report(self.cov_exmp, ''))

  def test_invalid_project_json(self):
    """Test a project json coverage report will be None."""
    self.assertIsNone(
        cifuzz.get_target_coverage_report('not-a-proj', self.example_fuzzer))
    self.assertIsNone(cifuzz.get_target_coverage_report('',
                                                        self.example_fuzzer))


class GetLatestCoverageReportUnitTest(unittest.TestCase):
  """Test get_latest_cov_report_info function in the cifuzz module."""

  test_project = 'curl'

  def test_get_valid_project(self):
    """Tests that a project's coverage report can be downloaded and parsed.

    NOTE: This test relies on the test_project repo's coverage report.
    Example was not used because it has no coverage reports.
    """
    with unittest.mock.patch.object(cifuzz,
                                    'get_json_from_url',
                                    return_value='{}') as mock_fun:

      cifuzz.get_latest_cov_report_info(self.test_project)
      (url,), _ = mock_fun.call_args
      self.assertEqual(
          'https://storage.googleapis.com/oss-fuzz-coverage/'
          'latest_report_info/curl.json', url)

  def test_get_invalid_project(self):
    """Tests a project's coverage report will return None if bad project."""
    self.assertIsNone(cifuzz.get_latest_cov_report_info('not-a-proj'))
    self.assertIsNone(cifuzz.get_latest_cov_report_info(''))


class KeepAffectedFuzzersUnitTest(unittest.TestCase):
  """Test the keep_affected_fuzzer detection in the CIFuzz module."""

  test_fuzzer_1 = os.path.join(TEST_FILES_PATH, 'out', 'example_crash_fuzzer')
  test_fuzzer_2 = os.path.join(TEST_FILES_PATH, 'out', 'example_nocrash_fuzzer')
  example_file_changed = 'test.txt'

  def test_keeping_specific_fuzzer(self):
    """Tests that a specific fuzzer is kept if it is deemed affected."""
    with tempfile.TemporaryDirectory() as tmp_dir, unittest.mock.patch.object(
        cifuzz, 'get_latest_cov_report_info', return_value=1):
      shutil.copy(self.test_fuzzer_1, tmp_dir)
      shutil.copy(self.test_fuzzer_2, tmp_dir)
      with unittest.mock.patch.object(cifuzz,
                                      'get_files_covered_by_target',
                                      side_effect=[[self.example_file_changed],
                                                   None]):
        cifuzz.keep_affected_fuzzers(EXAMPLE_PROJECT, tmp_dir,
                                     [self.example_file_changed], '')
        self.assertEqual(1, len(os.listdir(tmp_dir)))

  def test_no_fuzzers_kept_fuzzer(self):
    """Tests that if there is no affected then all fuzzers are kept."""
    with tempfile.TemporaryDirectory() as tmp_dir, unittest.mock.patch.object(
        cifuzz, 'get_latest_cov_report_info', return_value=1):
      shutil.copy(self.test_fuzzer_1, tmp_dir)
      shutil.copy(self.test_fuzzer_2, tmp_dir)
      with unittest.mock.patch.object(cifuzz,
                                      'get_files_covered_by_target',
                                      side_effect=[None, None]):
        cifuzz.keep_affected_fuzzers(EXAMPLE_PROJECT, tmp_dir,
                                     [self.example_file_changed], '')
        self.assertEqual(2, len(os.listdir(tmp_dir)))

  def test_both_fuzzers_kept_fuzzer(self):
    """Tests that if both fuzzers are affected then all fuzzers are kept."""
    with tempfile.TemporaryDirectory() as tmp_dir, unittest.mock.patch.object(
        cifuzz, 'get_latest_cov_report_info', return_value=1):
      shutil.copy(self.test_fuzzer_1, tmp_dir)
      shutil.copy(self.test_fuzzer_2, tmp_dir)
      with unittest.mock.patch.object(
          cifuzz,
          'get_files_covered_by_target',
          side_effect=[self.example_file_changed, self.example_file_changed]):
        cifuzz.keep_affected_fuzzers(EXAMPLE_PROJECT, tmp_dir,
                                     [self.example_file_changed], '')
        self.assertEqual(2, len(os.listdir(tmp_dir)))


if __name__ == '__main__':
  unittest.main()
