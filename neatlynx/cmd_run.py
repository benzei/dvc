import os
import shutil
import fasteners

from neatlynx.data_file_obj import DataFileObj, NotInDataDirError
from neatlynx.git_wrapper import GitWrapper
from neatlynx.cmd_base import CmdBase
from neatlynx.logger import Logger
from neatlynx.exceptions import NeatLynxException
from neatlynx.repository_change import RepositoryChange
from neatlynx.state_file import StateFile


class RunError(NeatLynxException):
    def __init__(self, msg):
        NeatLynxException.__init__(self, 'Run error: {}'.format(msg))


class CmdRun(CmdBase):
    def __init__(self):
        CmdBase.__init__(self)
        pass

    def define_args(self, parser):
        self.set_skip_git_actions(parser)

        parser.add_argument('--random', help='not reproducible, output is random', action='store_true')
        parser.add_argument('--stdout', help='output std output to a file')
        parser.add_argument('--stderr', help='output std error to a file')
        parser.add_argument('--input-file', '-i', action='append',
                            help='Declare input file for reproducible command')
        parser.add_argument('--output-file', '-o', action='append',
                            help='Declare output file for reproducible command')
        pass

    @property
    def declaration_input_files(self):
        if self.args.input_file:
            return self.args.input_file
        return []

    @property
    def declaration_output_files(self):
        if self.args.output_file:
            return self.args.output_file
        return []

    def run(self):
        lock = fasteners.InterProcessLock(self.git.lock_file)
        gotten = lock.acquire(timeout=5)
        if not gotten:
            Logger.printing('Cannot perform the command since NLX is busy and locked. Please retry the command later.')
            return 1

        try:
            if not self.skip_git_actions and not self.git.is_ready_to_go():
                return 1

            if not self.run_command(self._args_unkn, self.args.stdout, self.args.stderr):
                return 1

            if self.skip_git_actions:
                self.not_committed_changes_warning()
                return 0

            message = 'NLX run: {}'.format(' '.join(sys.argv))
            self.git.commit_all_changes_and_log_status(message)
        finally:
            lock.release()

        return 0

    def run_command(self, argv, stdout=None, stderr=None):
        repo_change = RepositoryChange(argv, stdout, stderr, self.git, self.config)

        if not self.skip_git_actions and not self.validate_file_states(repo_change):
            self.remove_new_files(repo_change)
            return False

        output_files = self.git.abs_paths_to_nlx(repo_change.new_files + self.declaration_output_files)
        input_files_from_args = list(set(self.get_data_files_from_args(argv)) - set(repo_change.new_files))
        input_files = self.git.abs_paths_to_nlx(input_files_from_args + self.declaration_input_files)

        for dobj in repo_change.dobj_for_new_files:
            os.makedirs(os.path.dirname(dobj.cache_file_relative), exist_ok=True)

            Logger.debug('Move output file "{}" to cache dir "{}" and create a symlink'.format(
                dobj.data_file_relative, dobj.cache_file_relative))
            shutil.move(dobj.data_file_relative, dobj.cache_file_relative)

            dobj.create_symlink()

            Logger.debug('Create state file "{}"'.format(dobj.state_file_relative))
            state_file = StateFile(dobj.state_file_relative, self.git, input_files, output_files)
            state_file.save()
            pass

        return True

    @staticmethod
    def remove_new_files(repo_change):
        for file in repo_change.new_files:
            rel_path = GitWrapper.abs_paths_to_relative([file])[0]
            Logger.error('Removing created file: {}'.format(rel_path))
            os.remove(file)
        pass

    def validate_file_states(self, files_states):
        error = False
        for file in GitWrapper.abs_paths_to_relative(files_states.removed_files):
            Logger.error('Error: file "{}" was removed'.format(file))
            error = True

        for file in GitWrapper.abs_paths_to_relative(files_states.modified_files):
            Logger.error('Error: file "{}" was modified'.format(file))
            error = True

        for file in GitWrapper.abs_paths_to_relative(files_states.unusual_state_files):
            Logger.error('Error: file "{}" is in not acceptable state'.format(file))
            error = True

        for file in GitWrapper.abs_paths_to_relative(files_states.externally_created_files):
            Logger.error('Error: file "{}" was created outside of the data directory'.format(file))
            error = True

        if error:
            Logger.error('Errors occurred. ' + \
                         'Reproducible commands allow only file creation only in data directory "{}".'.
                         format(self.config.data_dir))
            return False

        if not files_states.new_files:
            Logger.error('Errors occurred. No files were changed in run command.')
            return False

        return True

    def get_data_files_from_args(self, argv):
        result = []

        for arg in argv:
            try:
                if os.path.isfile(arg):
                    DataFileObj(arg, self.git, self.config)
                    result.append(arg)
            except NotInDataDirError:
                pass

        return result


if __name__ == '__main__':
    import sys

    try:
        sys.exit(CmdRun().run())
    except NeatLynxException as e:
        Logger.error(e)
        sys.exit(1)