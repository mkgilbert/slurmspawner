#slurmspawner for Jupyterhub
This is a custom spawner for Jupyterhub that is designed for installations on clusters using Slurm scheduling software. Some of the code and inspiration for this came directly from [Andrea Zonca's blog post](http://zonca.github.io/2015/04/jupyterhub-hpc.html 'Run jupyterhub on a Supercomputer') where he explains his implementation for a spawner that uses SSH and Torque. His github repo is found [here](http://www.github.com/zonca/remotespawner 'RemoteSpawner'). 

##Version 0.0.3 Features Update
This version is testing against the current jupyterhub version (as of 1/7/16, unofficially 0.4.0). Some things I'm working on:
- Just getting it to play nice with jupyterhub at all
- Getting the options form to work, allowing people to choose different SBATCH options

##Dependencies
- This spawner creates slurm jobs when users log in, so it must be installed in an environment running Slurm.
- Also, jupyterhub and its dependencies must be installed. See [the jupyterhub readme](https://github.com/jupyter/jupyterhub/blob/master/README.md) for instructions on setting up jupyterhub

##Installation
1. from root directory of this repo (where setup.py is), run `pip install -e .`
2. add lines in jupyterhub_config.py 
   
   ```python
      c = get_config()
      c.JupyterHub.spawner_class = 'slurmspawner.SlurmSpawner'
   ```

##Configuration
There are several values you can set in jupyterhub_config.py that override the default Slurm SBATCH options that get submitted by SlurmSpawner. Currently, the variables you can change are:
- job_name (String)
- partition (String)
- memory (Integer)
- time (String in format dd-hh:mm:ss)
- qos (String)
- output (String output file. Note that this will be appended to /home/$USER, so any subdirectories must already exist in the user's home directory.)
- cpus_per_task (Integer)
- ntasks (Integer)

Some of the other SBATCH options are not included because they would interfere with how SlurmSpawner works. For example, `workdir` needs to be /home/$USER because this is where jupyterhub will land you when you log in. If the submitting user isn't the owner of `workdir` the job will fail silently. If you would like access to other directories, it may be easiest to use the `extra_launch_script` variable described below to create soft links for the user on submission of the SlurmSpawner job.


You can add more functionality to the basic job script by specifying a bash script snippet. This is done with the `extra_launch_script` variable. For example, if you would like to make sure the user has a certain binary added to their path when they log in and also make soft links to an nfs "scratch" directory, your "snippet" would look like:

```bash
   export PATH=/path/to/binary:${PATH}
   ln -s /scratch/${USER} ${HOME}
```
Now just add 
```python
   c.SlurmSpawner.extra_launch_script = /path/to/snippet
```
to your jupyterhub_config.py file and that's it! When you run jupyterhub and a user logs in, it will set the path and soft links every time.

##Logging
There is quite verbose debug logging in SlurmSpawner (probably too verbose), so when testing this out it might help to set `c.Spawner.debug = True` in jupyterhub_config.py. This way you can see exactly what script is being sent to Slurm, and the jobid and status of all running servers each time they are polled.


