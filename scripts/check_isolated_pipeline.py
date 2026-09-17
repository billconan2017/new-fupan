"""Create a disposable PostgreSQL cluster, migrate and run the integration suite.
Run with the project venv Python. Never connects to an existing database.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

backend = Path(__file__).resolve().parents[1] / 'backend'
pg_bin = os.environ.get('PG_BIN')
if not pg_bin:
    candidates = sorted(Path('/usr/lib/postgresql').glob('*/bin/initdb'))
    executable = shutil.which('initdb') or (str(candidates[-1]) if candidates else None)
    if not executable:
        raise SystemExit('Install PostgreSQL server tools or set PG_BIN to their directory.')
    pg_bin = str(Path(executable).parent)
pg_bin = Path(pg_bin)
with tempfile.TemporaryDirectory(prefix='fupan-test-') as tmp:
    cluster = Path(tmp) / 'cluster'
    socket = Path(tmp) / 'socket'
    socket.mkdir(mode=0o700)
    subprocess.run([str(pg_bin/'initdb'), '-D', str(cluster), '-A', 'trust', '--no-locale', '-E', 'UTF8'],
                   check=True, stdout=subprocess.DEVNULL)
    # No TCP listener; unique private directory prevents access by other OS users.
    subprocess.run([str(pg_bin/'pg_ctl'), '-D', str(cluster), '-l', str(Path(tmp)/'pg.log'),
                    '-o', f"-k {socket} -h '' -p 55439", '-w', 'start'], check=True, stdout=subprocess.DEVNULL)
    env = dict(os.environ, PG_HOST=str(socket), PG_PORT='55439', PG_USER=os.environ.get('USER', 'bill'),
               PG_DATABASE='postgres', PG_PASSWORD='', LIANGMAI_TOKEN='', SCHEDULER_ENABLED='false',
               FUPAN_TEST_DB='1', PYTHONPATH=str(backend))
    try:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=backend, env=env, check=True)
        subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=backend, env=env, check=True)
    finally:
        subprocess.run([str(pg_bin/'pg_ctl'), '-D', str(cluster), '-m', 'fast', '-w', 'stop'],
                       check=True, stdout=subprocess.DEVNULL)
