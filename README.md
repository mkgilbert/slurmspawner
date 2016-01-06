#slurmspawner for Jupyterhub
This is a custom spawner for Jupyterhub that is designed for installations on clusters using Slurm scheduling software. Some of the code and inspiration for this came directly from [Andrea Zonca's blog post](http://zonca.github.io/2015/04/jupyterhub-hpc.html 'Run jupyterhub on a Supercomputer') where he explains his implementation for a spawner that uses SSH and Torque. His github repo is found [here](http://www.github.com/zonca/remotespawner 'RemoteSpawner'). 

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
