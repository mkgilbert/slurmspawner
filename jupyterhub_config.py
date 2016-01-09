c = get_config()
import os

pjoin = os.path.join
runtime_dir = pjoin('/srv/jupyterhub') # 

c.JupyterHub.hub_ip = '172.16.2.1'
c.JupyterHub.proxy_api_ip = '172.16.2.1'
c.JupyterHub.proxy_api_port = 5432
c.JupyterHub.hub_port = 54321
c.JupyterHub.port = 443
c.JupyterHub.ssl_key = pjoin(runtime_dir, 'openssl/server.key')
c.JupyterHub.ssl_cert = pjoin(runtime_dir, 'openssl/server.crt')
c.JupyterHub.db_url = pjoin(runtime_dir, 'jupyterhub.sqlite')
c.JupyterHub.cookie_secret_file = pjoin(runtime_dir, 'jupyterhub_cookie_secret')
c.JupyterHub.config_file = 'jupyterhub_config.py'
c.JupyterHub.extra_log_file = pjoin('/var/log/jupyter/jupyterhub.log')
c.Spawner.debug = True

# SlurmSpawner-specific settings
c.JupyterHub.log_level='DEBUG'
c.JupyterHub.spawner_class = 'slurmspawner.SlurmSpawner'
c.SlurmSpawner.start_timeout = 1200  # make these numbers large enough so that they won't time out while waiting for slurm to start the job
c.SlurmSpawner.http_timeout = 1200
c.SlurmSpawner.extra_launch_script = pjoin('/etc/jupyterhub/extra_launch_script')

# Slurm SBATCH settings for the internally-created launch script.
# Extra functionality for your SlurmSpawner can be added through a script pointed to by c.SlurmSpawner.extra_launch_script
c.SlurmSpawner.job_name = "jupyterhub-singleuser"
c.SlurmSpawner.partition = 'all'
c.SlurmSpawner.mem = 350 # memory in MB
c.SlurmSpawner.time = "8:00:00" # Slurm-style time dd-hh:mm:ss
c.SlurmSpawner.qos = "jupyter"  # this must exist or jupyterhub will fail to start
c.SlurmSpawner.output = "jhub-spawner.log" # this file/dir is appended to /home/$USER/

