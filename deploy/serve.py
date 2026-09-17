"""Local production entrypoint. Configuration is outside Git and legacy folders."""
from pathlib import Path
import os
import subprocess
from dotenv import dotenv_values
repo=Path(__file__).resolve().parents[1]
config=Path(os.environ.get('GUANMAI_CONFIG',str(Path.home()/'.config/guanmai/runtime.env')))
env={**os.environ,**{k:v for k,v in dotenv_values(config).items() if v is not None}}
base=Path(env.get('GUANMAI_STATE',str(Path.home()/'.local/share/fupan-preview')))
pg=Path('/usr/lib/postgresql/16/bin')
if subprocess.run([str(pg/'pg_ctl'),'-D',str(base/'cluster'),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    subprocess.run([str(pg/'pg_ctl'),'-D',str(base/'cluster'),'-l',str(base/'postgres.log'),'-o',f"-k {base/'socket'} -h '' -p 55439",'-w','start'],check=True,stdout=subprocess.DEVNULL)
env.update(PG_HOST=str(base/'socket'),PG_PORT='55439',PG_USER='bill',PG_DATABASE='postgres',PG_PASSWORD='',SCHEDULER_ENABLED='false',REDIS_PORT='1',PYTHONPATH=str(repo/'backend'))
# Fail early instead of silently borrowing credentials or data from the old system.
if not env.get('LIANGMAI_TOKEN'):raise SystemExit('Missing LIANGMAI_TOKEN in local runtime configuration')
python=str(repo/'.venv/bin/python')
subprocess.run([python,'-m','alembic','upgrade','head'],cwd=repo/'backend',env=env,check=True)
os.chdir(repo/'backend')
os.execve(python,[python,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',env.get('GUANMAI_PORT','8899'),'--workers','1','--log-level','warning'],env)
