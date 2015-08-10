"""SlurmSpawner implementation"""
import signal
import errno
import pwd
import os
import time
import pipes
from subprocess import Popen, call
import subprocess
from string import Template
from concurrent.futures import ThreadPoolExecutor

from tornado import gen

from traitlets import (
    Instance, Integer, Unicode
)

from jupyterhub.spawner import Spawner
from jupyterhub.spawner import set_user_setuid
from jupyterhub.utils import random_port


def run_command(cmd):
    popen = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out = popen.communicate()
    if out[1] is not None:
        return out[1] # exit error?
    else:
        out = out[0].decode().strip()
        return out


class SlurmSpawner(Spawner):
    """A Spawner that just uses Popen to start local processes."""

    _executor = None
    @property
    def executor(self):
        """single global executor"""
        self.log.debug("Running executor...")
        cls = self.__class__
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(1)
        return cls._executor

    INTERRUPT_TIMEOUT = Integer(1200, config=True, \
        help="Seconds to wait for process to halt after SIGINT before proceeding to SIGTERM"
                               )
    TERM_TIMEOUT = Integer(1200, config=True, \
        help="Seconds to wait for process to halt after SIGTERM before proceeding to SIGKILL"
                          )
    KILL_TIMEOUT = Integer(1200, config=True, \
        help="Seconds to wait for process to halt after SIGKILL before giving up"
                          )

    ip = Unicode("0.0.0.0", config=True, \
        help="url of the server")

    slurm_job_id = Unicode() # will get populated after spawned

    pid = Integer(0)

    def make_preexec_fn(self, name):
        """make preexec fn"""
        return set_user_setuid(name)

    def load_state(self, state):
        """load slurm_job_id from state"""
        super(SlurmSpawner, self).load_state(state)
        self.slurm_job_id = state.get('slurm_job_id', '')
        self.slurm_port = state.get('slurm_port', '')

    def get_state(self):
        """add slurm_job_id to state"""
        state = super(SlurmSpawner, self).get_state()
        if self.slurm_job_id:
            state['slurm_job_id'] = self.slurm_job_id
        if self.slurm_port:
            state['slurm_port'] = self.slurm_port
        return state

    def clear_state(self):
        """clear slurm_job_id state"""
        super(SlurmSpawner, self).clear_state()
        self.slurm_job_id = ""
        self.slurm_port = ""

    def user_env(self, env):
        """get user environment"""
        env['USER'] = self.user.name
        env['HOME'] = pwd.getpwnam(self.user.name).pw_dir
        return env

    def _env_default(self):
        env = super()._env_default()
        return self.user_env(env)
    
    @gen.coroutine
    def stop_slurm_job(self):
        """Wrapper to call _stop_slurm_job() to be passed to ThreadPoolExecutor"""
        is_stopped = yield self.executor.submit(self._stop_slurm_job)
        return is_stopped
         
    def _stop_slurm_job(self):
        if self.slurm_job_id in (None, ""):
            self.log.warn("Slurm job id for user %s isn't defined!" % (self.user.name))
            return True

        cmd = 'scancel ' + self.slurm_job_id
        self.log.info("Cancelling slurm job %s for user %s" % (self.slurm_job_id, self.user.name))

        job_state = run_command(cmd)
        time.sleep(1)
        if job_state in ("CANCELLED", "COMPLETED", "FAILED", "COMPLETING"):
            return True
        else:
            #status = yield self.poll()
            #if status is None:
            #    self.log.warn("Job %s never cancelled" % self.slurm_job_id)
            return False

    #@gen.coroutine
    #def check_slurm_job_state(self):
    #    """Wrapper for calling _check_slurm_job_state() to be passed to ThreadPoolExecutor..."""
    #    self.log.debug("Checking slurm job %s" % self.slurm_job_id)
    #    status = yield self.executor.submit(self._check_slurm_job_state)
    #    return status

    def check_slurm_job_state(self):
        self.log.debug("Checking slurm job %s" % self.slurm_job_id)
        if self.slurm_job_id in (None, ""):
            # job has been cancelled or failed, so don't even try the squeue command. This is because
            # squeue will return RUNNING if you submit something like `squeue -h -j -o %T` and there's
            # at least 1 job running
            return ""
        # check sacct to see if the job is still running
        cmd = 'squeue -h -j ' + self.slurm_job_id + ' -o %T'
        out = run_command(cmd)
        self.log.debug("Notebook server for user %s: Slurm jobid %s status: %s" % (self.user.name, self.slurm_job_id, out))
        return out
        
    #def _check_slurm_job_state(self):
    #    if self.slurm_job_id in (None, ""):
    #        # job has been cancelled or failed, so don't even try the squeue command. This is because
    #        # squeue will return RUNNING if you submit something like `squeue -h -j -o %T` and there's
    #        # at least 1 job running
    #        return ""
    #    # check sacct to see if the job is still running
    #    cmd = 'squeue -h -j ' + self.slurm_job_id + ' -o %T'
    #    out = run_command(cmd)
    #    self.log.debug("Notebook server for user %s: Slurm jobid %s status: %s" % (self.user.name, self.slurm_job_id, out))
    #    return out

    def query_slurm_by_jobname(self, user, jobname):
        """
        uses slurm's squeue to see if there is currently a job called <jobname> running.
        If so, it returns the jobid
        """ 
        cmd = 'squeue -h -u %s --name=%s -O jobid,comment' % (user, jobname)
        self.log.debug("running command '%s'" % cmd)
        output = run_command(cmd).strip()
        output_list = output.split()
        self.log.debug("output list: %s" % output_list)
        if len(output_list) > 0:
            jobid = output_list[0]
            port = output_list[1]
        else:
            return ("", "")
        self.log.debug("Queried slurm for user=%s jobname=%s and found jobid '%s'" % (user, 
                                                                                      jobname, 
                                                                                      jobid))
        return (jobid, port)

    @gen.coroutine
    def run_jupyterhub_singleuser(self, cmd, port, user):
        """ 
        Wrapper for calling run_jupyterhub_singleuser to be passed to ThreadPoolExecutor..
        """
        args = [cmd, port, user]
        self.log.debug("Now we're in the run_jupyterhub_singleuser method...")
        server = yield self.executor.submit(self._run_jupyterhub_singleuser, *args)
        return server

    def _run_jupyterhub_singleuser(self, cmd, port, user):
        """
        Submits a slurm sbatch script to start jupyterhub-singleuser
        """
        self.log.debug("Now we're in the jupyterhub_singleuser method...")
        sbatch = Template('''#!/bin/bash
#SBATCH --partition=$queue
#SBATCH --time=$hours:00:00
#SBATCH -o /home/$user/jupyterhub_slurmspawner_%j.log
#SBATCH --job-name=spawner-jupyterhub-singleuser
#SBATCH --comment=$port
#SBATCH --workdir=/home/$user
#SBATCH --mem=$mem
#SBATCH --uid=$user
#SBATCH --get-user-env=L

which jupyterhub-singleuser
$export_cmd
$cmd
        ''')
        self.slurm_job_id = '51'
        #return self.slurm_job_id
        queue = "all"
        mem = '200'
        hours = '2'
        full_cmd = cmd.split(';')
        export_cmd = full_cmd[0] 
        cmd = full_cmd[1]
        sbatch = sbatch.substitute(dict(export_cmd=export_cmd, 
                                        cmd=cmd, 
                                        port=port,
                                        queue=queue, 
                                        mem=mem, 
                                        hours=hours, 
                                        user=user))

        print('Submitting *****{\n%s\n}*****' % sbatch)
        popen = subprocess.Popen('sbatch', 
                                 shell = True, stdin = subprocess.PIPE, 
                                 stdout = subprocess.PIPE)
        output = popen.communicate(sbatch.encode())[0].strip() #e.g. something like "Submitted batch job 209"
        output = output.decode() # convert bytes object to string
        self.log.debug("Stdout of trying to call sbatch: %s" % output)
        self.slurm_job_id = output.split(' ')[-1] # the job id should be the very last part of the string

        job_state = self.check_slurm_job_state()
        while True:
            self.log.info("job_state is %s" % job_state)
            if 'RUNNING' in job_state:
                break
            elif 'PENDING' in job_state:
                job_state = self.check_slurm_job_state()
                time.sleep(1)
            else:
                self.log.info("Job %s failed to start!" % self.slurm_job_id)
                return 1 # is this right? Or should I not return, or return a different thing?
        return self.slurm_job_id

    def get_slurm_job_info(self, jobid):
        """returns ip address of node that is running the job"""
        cmd = 'squeue -h -j ' + jobid + ' -o %N'
        popen = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        node_name = popen.communicate()[0].strip().decode() # convett bytes object to string
        # now get the ip address of the node name
        if node_name in (None, ""):
            return (None, None)
        cmd = 'host %s' % node_name
        popen = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        out = popen.communicate()[0].strip().decode()
        node_ip = out.split(' ')[-1] # the last portion of the output should be the ip address
        return (node_ip, node_name)

    @gen.coroutine
    def start(self):
        """Start the process"""
        # first check if the user has a spawner running somewhere on the server
        jobid, port = self.query_slurm_by_jobname(self.user.name, 'spawner-jupyterhub-singleuser')
        self.slurm_job_id = jobid
        self.user.server.port = port
        if jobid != "" and port != "":
            self.log.debug("Server was found running with slurm jobid '%s' \
                            for user '%s' on port %s" % (jobid, self.user.name, port)) 
            node_ip, node_name = self.get_slurm_job_info(jobid)
            self.user.server.ip = node_ip
            return

        # if the above wasn't true, then it didn't find a state for the user
        self.user.server.port = random_port()

        cmd = []
        env = self.env.copy()

        cmd.extend(self.cmd)
        cmd.extend(self.get_args())

        self.log.debug("Env: %s", str(env))
        self.log.info("Spawning %s", ' '.join(cmd))
        for k in ["JPY_API_TOKEN"]:
            cmd.insert(0, 'export %s="%s";' % (k, env[k]))

        output = yield self.run_jupyterhub_singleuser(' '.join(cmd),
                                                      self.user.server.port,
                                                      self.user.name)
        
        if output == 1:
            self.log.error("Slurm job never started, exited with error 1")
            return
        #output = output.decode() # convert bytes object to string
        #self.log.debug("Stdout of trying to call run_jupyterhub_singleuser(): %s" % output)
        #self.slurm_job_id = output.split(' ')[-1] # the job id should be the very last part of the string

        # make sure jobid is really a number
        try:
            int(self.slurm_job_id)
        except ValueError:
            self.log.error("sbatch returned this at the end of their string: %s" % self.slurm_job_id)
            return 1
        #job_state = yield self.check_slurm_job_state()
       # for i in range(5):
       #     self.log.info("job_state is %s" % job_state)
       #     if 'RUNNING' in job_state:
       #         break
       #     elif 'PENDING' in job_state:
       #         job_state = yield self.check_slurm_job_state()
       #         time.sleep(1)
       #     else:
       #         self.log.info("Job %s failed to start!" % self.slurm_job_id)
       #         return 1 # is this right? Or should I not return, or return a different thing?
         
        node_ip, node_name  = self.get_slurm_job_info(self.slurm_job_id)
        #if node_ip is None or node_name is None:
        #    return 1 # slurm job didn't submit
        self.user.server.ip = node_ip 
        self.log.info("Notebook server running on %s (%s)" % (node_name, node_ip))

    @gen.coroutine
    def poll(self):
        """Poll the process"""
        if self.slurm_job_id is not None:
            state = self.check_slurm_job_state()
            if "RUNNING" in state or "PENDING" in state:
                return None
            else:
                self.clear_state()
                return 1

        if not self.slurm_job_id:
            # no job id means it's not running
            self.clear_state()
            return 1

    @gen.coroutine
    def _signal(self, sig):
        """simple implementation of signal

        we can use it when we are using setuid (we are root)"""
        return True

    #@gen.coroutine
    #def stop(self, now=False):
    #    """stop the subprocess

    #    if `now`, skip waiting for clean shutdown
    #    """
    #    #status = yield self.poll()
    #    if status is not None:
    #        # job is not running
    #        return

    #    cmd = 'scancel ' + self.slurm_job_id
    #    self.log.info("Cancelling slurm job %s for user %s" % (self.slurm_job_id, self.user.name))

    #    job_state = run_command(cmd)
    #    
    #    if job_state in ("CANCELLED", "COMPLETED", "FAILED", "COMPLETING"):
    #        return
    #    else:
    #        status = yield self.poll()
    #        if status is None:
    #            self.log.warn("Job %s never cancelled" % self.slurm_job_id)

    @gen.coroutine
    def stop(self, now=False):
        if now:
            self.log.info("Stopping slurm job %s for user %s" % (self.slurm_job_id, self.user.name))
            is_stopped = yield self.stop_slurm_job()
            if not is_stopped:
                self.log.warn("Job %s didn't stop. Trying again..." % self.slurm_job_id)
                yield self.stop_slurm_job()
        
        self.clear_state()
