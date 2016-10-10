from .slurmspawner import *
import shlex

class FormSpawner(SlurmSpawner):
    def _options_form_default(self):
        default_env = "YOURNAME=%s\n" % self.user.name
        return """
        <label for="args">Cluster Slurm arguments</label>
        <input name="args" placeholder="e.g. --ntasks=4"></input>
        """.format()

    def options_from_form(self, formdata):
        arg_s = formdata.get('args', [''])[0].strip()
        if arg_s:
            options['argv'] = shlex.split(arg_s)
        return options

    def get_args(self):
        argv = super().get_args()
        if self.user_options.get('argv'):
            argv.extend(self.user_options['argv'])
        return argv

